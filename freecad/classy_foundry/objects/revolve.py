"""Tier 2 'Revolve' Document Object: a thin wrapper around classy_blocks' Revolve."""

import math

import classy_blocks as cb
import FreeCAD

from .recording import (
    OperationProxyBase,
    OperationViewProviderBase,
    RecordingOperationMixin,
    add_chop_patch_properties,
)


class RecordingRevolve(RecordingOperationMixin, cb.Revolve):
    """A cb.Revolve that remembers its base Face's varname and angle/axis/origin for codegen."""

    def __init__(self, base, angle_deg, axis, origin, base_varname):
        self.angle_deg = angle_deg
        self.axis = axis
        self.origin = origin
        self.base_varname = base_varname
        super().__init__(base, math.radians(angle_deg), axis, origin)
        self.referenced_faces = {base_varname: base}

    def to_lines(self, varname: str) -> list[str]:
        angle_rad = math.radians(self.angle_deg)
        lines = [
            f"{varname} = cb.Revolve({self.base_varname}, {angle_rad!r}, "
            f"{list(self.axis)}, {list(self.origin)})  # angle: {self.angle_deg} deg"
        ]
        lines.extend(self.chop_patch_lines(varname))
        return lines


class RevolveProxy(OperationProxyBase):
    """Proxy for a Part::FeaturePython object representing a classy_blocks Revolve."""

    FACE_LINKS = ("Base",)

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLink", "Base", "ClassyFoundry", "Face to revolve"
        )
        obj.addProperty(
            "App::PropertyAngle", "Angle", "ClassyFoundry", "Revolve angle"
        ).Angle = 90
        obj.addProperty(
            "App::PropertyVector", "Axis", "ClassyFoundry", "Revolve axis direction"
        ).Axis = FreeCAD.Vector(0, 0, 1)
        obj.addProperty(
            "App::PropertyVector", "Origin", "ClassyFoundry", "Point the revolve axis passes through"
        ).Origin = FreeCAD.Vector(0, 0, 0)
        add_chop_patch_properties(obj)

    def build_operation(self, obj, base_face):
        axis = [obj.Axis.x, obj.Axis.y, obj.Axis.z]
        origin = [obj.Origin.x, obj.Origin.y, obj.Origin.z]
        return RecordingRevolve(base_face, obj.Angle, axis, origin, obj.Base.Name.lower())


class RevolveViewProvider(OperationViewProviderBase):
    """Minimal ViewProvider so the Revolve's Shape renders in the 3D view."""


def make_revolve(doc, name="Revolve"):
    """Create a new Revolve Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    RevolveProxy(obj)
    if FreeCAD.GuiUp:
        RevolveViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
