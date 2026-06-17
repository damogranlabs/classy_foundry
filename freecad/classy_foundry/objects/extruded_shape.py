"""Tier 2 'ExtrudedShape' Document Object: extrudes a MappedSketch into a Shape."""

import classy_blocks as cb
import FreeCAD

from .recording import ProxyBase, ViewProviderBase, hide, resolve_sketch, solid_preview_shape


class ExtrudedShapeProxy(ProxyBase):
    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLink", "Sketch", "ClassyFoundry",
            "MappedSketch to extrude",
        )
        obj.addProperty(
            "App::PropertyFloat", "Amount", "ClassyFoundry",
            "Extrusion distance along sketch normal",
        ).Amount = 1.0
        for axis_name in ("X", "Y", "Z"):
            obj.addProperty(
                "App::PropertyInteger",
                f"ChopCount{axis_name}",
                "Chop",
                f"Number of cells along the {axis_name} axis (0 = not chopped)",
            )

    def execute(self, obj):
        sketch = resolve_sketch(obj.Sketch)
        if sketch is None:
            return

        self.shape = cb.ExtrudedShape(sketch, obj.Amount)
        for axis, axis_name in enumerate(("X", "Y", "Z")):
            count = getattr(obj, f"ChopCount{axis_name}")
            if count > 0:
                self.shape.chop(axis, count=count)

        obj.Shape = solid_preview_shape(self.shape)
        hide(obj.Sketch)

    def to_lines(self, obj, varname):
        sketch_obj = obj.Sketch
        if sketch_obj is None:
            return []
        sketch_varname = sketch_obj.Name.lower()
        lines = [f"{varname} = cb.ExtrudedShape({sketch_varname}, {obj.Amount})"]
        for axis, axis_name in enumerate(("X", "Y", "Z")):
            count = getattr(obj, f"ChopCount{axis_name}")
            if count > 0:
                lines.append(f"{varname}.chop({axis}, count={count})")
        return lines


class ExtrudedShapeViewProvider(ViewProviderBase):
    def claimChildren(self):
        children = []
        sketch = self.Object.Sketch
        if sketch is not None:
            children.append(sketch)
        return children


def make_extruded_shape(doc, name="ExtrudedShape"):
    """Create a new ExtrudedShape Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    ExtrudedShapeProxy(obj)
    if FreeCAD.GuiUp:
        ExtrudedShapeViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
