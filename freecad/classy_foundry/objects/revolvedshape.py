"""'RevolvedShape' Document Object: revolves a MappedSketch around an axis."""

import math

import classy_blocks as cb
import FreeCAD

from .recording import AxisVisualizationMixin, ProxyBase, ViewProviderBase, resolve_sketch, revolve_preview_shape


class RevolvedShapeProxy(ProxyBase):
    SKETCH_LINKS = ("Sketch",)

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty("App::PropertyLink", "Sketch", "ClassyFoundry", "MappedSketch to revolve")
        obj.addProperty("App::PropertyAngle", "Angle", "ClassyFoundry", "Revolve angle").Angle = 90
        obj.addProperty(
            "App::PropertyVector", "Axis", "ClassyFoundry", "Revolve axis direction"
        ).Axis = FreeCAD.Vector(0, 0, 1)
        obj.addProperty(
            "App::PropertyVector", "Origin", "ClassyFoundry", "Point the revolve axis passes through"
        )

    def execute(self, obj):
        sketch = resolve_sketch(obj.Sketch)
        if sketch is None:
            return
        a, o = obj.Axis, obj.Origin
        self.shape = cb.RevolvedShape(
            sketch,
            math.radians(float(obj.Angle)),
            [a.x, a.y, a.z],
            [o.x, o.y, o.z],
        )
        obj.Shape = revolve_preview_shape(self.shape.operations, obj.Origin, obj.Axis, float(obj.Angle))

    def to_lines(self, obj, varname):
        sketch_obj = obj.Sketch
        if sketch_obj is None:
            return []
        a, o = obj.Axis, obj.Origin
        angle_rad = math.radians(float(obj.Angle))
        return [
            f"{varname} = cb.RevolvedShape("
            f"{sketch_obj.Name.lower()}, {angle_rad!r}, "
            f"{[a.x, a.y, a.z]}, {[o.x, o.y, o.z]}"
            f")  # angle: {obj.Angle} deg"
        ]


class RevolvedShapeViewProvider(AxisVisualizationMixin, ViewProviderBase):
    pass


def make_revolved_shape(doc, name="RevolvedShape"):
    """Create a new RevolvedShape Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    RevolvedShapeProxy(obj)
    if FreeCAD.GuiUp:
        RevolvedShapeViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
