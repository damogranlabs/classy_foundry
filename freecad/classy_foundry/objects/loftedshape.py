"""'LoftedShape' Document Object: lofts between two MappedSketches."""

import classy_blocks as cb
import FreeCAD

from .recording import ProxyBase, ViewProviderBase, resolve_sketch, solid_preview_shape


def _walk_sketch_chain(link_obj):
    """Resolve a cb.MappedSketch from link_obj, walking Copy/Transform chains.

    Returns (cb_sketch, varname, prep_lines):
    - cb_sketch: resolved sketch with any transforms applied, or None
    - varname: Python variable name to use in generated code
    - prep_lines: lines to emit before varname (copy + transform calls)
    """
    from .transform import _apply as _apply_xform, _transform_call

    if link_obj is None:
        return None, None, []

    modifiers = []
    copy_obj = None
    current = link_obj

    while current is not None:
        sketch = getattr(getattr(current, "Proxy", None), "sketch", None)
        if sketch is not None:
            if copy_obj is None:
                return sketch, current.Name.lower(), []
            copy_varname = copy_obj.Name.lower()
            result = sketch.copy()
            prep_lines = [f"{copy_varname} = {current.Name.lower()}.copy()"]
            for mod in reversed(modifiers):
                _apply_xform(mod, result)
                prep_lines.append(f"{copy_varname}.{_transform_call(mod)}")
            return result, copy_varname, prep_lines

        if hasattr(current, "CopyOf"):
            copy_obj = current
            current = current.CopyOf
        elif hasattr(current, "Source"):
            modifiers.append(current)
            current = current.Source
        else:
            return None, None, []

    return None, None, []


class LoftedShapeProxy(ProxyBase):
    SKETCH_LINKS = ("Sketch1", "Sketch2")

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty("App::PropertyLink", "Sketch1", "ClassyFoundry", "Start MappedSketch")
        obj.addProperty("App::PropertyLink", "Sketch2", "ClassyFoundry", "End MappedSketch or Copy/Transform thereof")

    def execute(self, obj):
        sketch1 = resolve_sketch(obj.Sketch1)
        sketch2, _, _ = _walk_sketch_chain(obj.Sketch2)
        if sketch1 is None or sketch2 is None:
            return
        self.shape = cb.LoftedShape(sketch1, sketch2)
        obj.Shape = solid_preview_shape(self.shape)

    def to_lines(self, obj, varname):
        if obj.Sketch1 is None or obj.Sketch2 is None:
            return []
        _, sketch2_varname, prep_lines = _walk_sketch_chain(obj.Sketch2)
        if sketch2_varname is None:
            return []
        return prep_lines + [f"{varname} = cb.LoftedShape({obj.Sketch1.Name.lower()}, {sketch2_varname})"]


class LoftedShapeViewProvider(ViewProviderBase):
    pass


def make_lofted_shape(doc, name="LoftedShape"):
    """Create a new LoftedShape Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    LoftedShapeProxy(obj)
    if FreeCAD.GuiUp:
        LoftedShapeViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
