"""Tier 1 'Face' Document Object: a thin wrapper around classy_blocks' Face."""

import classy_blocks as cb
import FreeCAD

from .recording import FaceProxyBase, ViewProviderBase


class RecordingFace(cb.Face):
    """A cb.Face that remembers its constructor args for later codegen."""

    def __init__(self, points):
        self.points_arg = points
        super().__init__(points, edges=None)

    def to_lines(self, varname: str) -> list[str]:
        return [f"{varname} = cb.Face({[list(p) for p in self.points_arg]})"]


class FaceProxy(FaceProxyBase):
    """Proxy for a Part::FeaturePython object representing a classy_blocks Face."""

    def __init__(self, obj):
        obj.Proxy = self
        defaults = (
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(1, 0, 0),
            FreeCAD.Vector(1, 1, 0),
            FreeCAD.Vector(0, 1, 0),
        )
        for i, default in enumerate(defaults, start=0):
            obj.addProperty(
                "App::PropertyVector",
                f"Point{i}",
                "ClassyFoundry",
                f"Corner {i} of the face",
            )
            setattr(obj, f"Point{i}", default)

    def build_face(self, obj):
        points = [
            [obj.Point0.x, obj.Point0.y, obj.Point0.z],
            [obj.Point1.x, obj.Point1.y, obj.Point1.z],
            [obj.Point2.x, obj.Point2.y, obj.Point2.z],
            [obj.Point3.x, obj.Point3.y, obj.Point3.z],
        ]
        return RecordingFace(points)


class FaceViewProvider(ViewProviderBase):
    """Minimal ViewProvider so the Face's Shape renders in the 3D view."""


def make_face(doc, name="Face"):
    """Create a new Face Document Object in `doc`, at document root."""
    obj = doc.addObject("Part::FeaturePython", name)
    FaceProxy(obj)
    if FreeCAD.GuiUp:
        FaceViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
