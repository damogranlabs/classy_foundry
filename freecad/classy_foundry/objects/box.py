"""Tier 2 'Box' Document Object: a thin wrapper around classy_blocks' Box."""

import classy_blocks as cb
import FreeCAD

from .recording import (
    OperationProxyBase,
    OperationViewProviderBase,
    RecordingOperationMixin,
    add_chop_properties,
)


class RecordingBox(RecordingOperationMixin, cb.Box):
    """A cb.Box that remembers its constructor args and chop()/set_patch() calls."""

    def __init__(self, start_point, diagonal_point):
        self.start_point = start_point
        self.diagonal_point = diagonal_point
        super().__init__(start_point, diagonal_point)

    def to_lines(self, varname: str) -> list[str]:
        lines = [f"{varname} = cb.Box({list(self.start_point)}, {list(self.diagonal_point)})"]
        lines.extend(self.chop_lines(varname))
        return lines


class BoxProxy(OperationProxyBase):
    """Proxy for a Part::FeaturePython object representing a classy_blocks Box."""

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyVector", "Point1", "ClassyFoundry", "One corner of the box"
        ).Point1 = FreeCAD.Vector(0, 0, 0)
        obj.addProperty(
            "App::PropertyVector", "Point2", "ClassyFoundry", "Corner diagonally opposite Point1"
        ).Point2 = FreeCAD.Vector(1, 1, 1)
        add_chop_properties(obj)

    def build_operation(self, obj):
        return RecordingBox(
            [obj.Point1.x, obj.Point1.y, obj.Point1.z],
            [obj.Point2.x, obj.Point2.y, obj.Point2.z],
        )


class BoxViewProvider(OperationViewProviderBase):
    """Minimal ViewProvider so the Box's Shape renders in the 3D view."""


def make_box(doc, name="Box"):
    """Create a new Box Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    BoxProxy(obj)
    if FreeCAD.GuiUp:
        BoxViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
