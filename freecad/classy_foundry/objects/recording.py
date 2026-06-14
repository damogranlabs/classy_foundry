"""Shared helpers for 'recording' classy_blocks Operation subclasses and their proxies.

cb.Box, cb.Loft and cb.Extrude (and later cb.Revolve, cb.Wedge, ...) are all
cb.Operation subclasses and share the same chop()/set_patch() surface, as well
as the same FreeCAD ChopCount*/Patch* properties. This module factors that
shared surface out so each RecordingX/XProxy pair only has to deal with its
own constructor arguments.
"""

import FreeCAD
import Part

CHOP_PATCH_SIDES = ("Bottom", "Top", "Left", "Right", "Front", "Back")


class RecordingOperationMixin:
    """Records chop()/set_patch() calls (and referenced Faces) for later codegen."""

    def __init__(self, *args, **kwargs):
        self.recorded_chops: list[tuple[int, dict]] = []
        self.recorded_patches: list[tuple[str, str]] = []
        self.referenced_faces: dict = {}
        super().__init__(*args, **kwargs)

    def chop(self, axis, **kwargs):
        super().chop(axis, **kwargs)
        self.recorded_chops.append((axis, kwargs))

    def set_patch(self, sides, name):
        super().set_patch(sides, name)
        self.recorded_patches.append((sides, name))

    def chop_patch_lines(self, varname: str) -> list[str]:
        """Codegen lines for recorded chop()/set_patch() calls, in recording order."""
        lines = []
        for axis, kwargs in self.recorded_chops:
            args = ", ".join(f"{key}={value!r}" for key, value in kwargs.items())
            lines.append(f"{varname}.chop({axis}, {args})")
        for sides, name in self.recorded_patches:
            lines.append(f"{varname}.set_patch({sides!r}, {name!r})")
        return lines


def add_chop_patch_properties(obj):
    """Add the standard ChopCountX/Y/Z and Patch* properties to a Tier 2 object."""
    for axis_name in ("X", "Y", "Z"):
        obj.addProperty(
            "App::PropertyInteger",
            f"ChopCount{axis_name}",
            "Chop",
            f"Number of cells along the {axis_name} axis (0 = not chopped)",
        )
    for side in CHOP_PATCH_SIDES:
        obj.addProperty(
            "App::PropertyString",
            f"Patch{side}",
            "Patches",
            f"Patch name for the '{side.lower()}' side (empty = not set)",
        )


def apply_chop_patch(obj, operation):
    """Replay an object's ChopCount*/Patch* properties onto a recording operation."""
    for axis, axis_name in enumerate(("X", "Y", "Z")):
        count = getattr(obj, f"ChopCount{axis_name}")
        if count > 0:
            operation.chop(axis, count=count)
    for side in CHOP_PATCH_SIDES:
        name = getattr(obj, f"Patch{side}")
        if name:
            operation.set_patch(side.lower(), name)


def loft_preview_shape(operation) -> Part.Shape:
    """Straight-edge preview (Tier B) lofted between an operation's bottom and top faces."""
    bottom = [FreeCAD.Vector(*p.position) for p in operation.bottom_face.points]
    top = [FreeCAD.Vector(*p.position) for p in operation.top_face.points]
    bottom_wire = Part.makePolygon([*bottom, bottom[0]])
    top_wire = Part.makePolygon([*top, top[0]])
    return Part.makeLoft([bottom_wire, top_wire], True)
