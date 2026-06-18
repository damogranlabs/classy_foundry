"""Tier 2 'ExtrudedShape' Document Object: extrudes a MappedSketch into a Shape."""

import classy_blocks as cb
import FreeCAD

from .recording import ProxyBase, ViewProviderBase, resolve_sketch, solid_preview_shape


class ExtrudedShapeProxy(ProxyBase):
    SKETCH_LINKS = ("Sketch",)

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

    def execute(self, obj):
        sketch = resolve_sketch(obj.Sketch)
        if sketch is None:
            return

        self.shape = cb.ExtrudedShape(sketch, obj.Amount)
        obj.Shape = solid_preview_shape(self.shape)

    def to_lines(self, obj, varname):
        sketch_obj = obj.Sketch
        if sketch_obj is None:
            return []
        sketch_varname = sketch_obj.Name.lower()
        return [f"{varname} = cb.ExtrudedShape({sketch_varname}, {obj.Amount})"]


class ExtrudedShapeViewProvider(ViewProviderBase):
    pass


def make_extruded_shape(doc, name="ExtrudedShape"):
    """Create a new ExtrudedShape Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    ExtrudedShapeProxy(obj)
    if FreeCAD.GuiUp:
        ExtrudedShapeViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
