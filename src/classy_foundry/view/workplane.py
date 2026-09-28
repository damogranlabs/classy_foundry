"""The work plane: where a click lands, and what the scene is cut against.

It is **polyscope's own slice plane**, not state of ours. Polyscope already gives it a pose,
a drawn grid, a transparency, a colour, a draggable widget and per-structure exemptions, so
the plane's pose is the single source of truth: dragging the widget, typing numbers and
following the camera all write to the same place and nothing can fall out of sync.

Two things polyscope cannot know, and they are all this module owns:

- whether the plane should **follow the camera** (handy for aiming) or **stay put** (needed
  for placing several points on one plane -- if it rotated with the view, coplanar points
  would be impossible);
- that points and the move gizmo must **never be cut away**, or the plane would eat the
  very things being placed.

An *inactive* slice plane cannot hold a pose -- polyscope parks it at infinity -- so the
plane is always active and "does it cut?" is expressed the only way that works: by
exempting structures. Nothing cuts when the answer is no.
"""

from typing import Optional

import numpy as np
import polyscope as ps
import polyscope.imgui as psim

from ..geom import Plane

NAME = "work plane"
TRANSPARENCY = 0.25
GRID_COLOR = (0.55, 0.62, 0.7)

# Quick orientations: what a normal is for each pair of axes to lie in the plane.
ORIENTATIONS = {"XY": (0.0, 0.0, 1.0), "XZ": (0.0, 1.0, 0.0), "YZ": (1.0, 0.0, 0.0)}

# Structures a cut must never touch: the points being placed, and the move gizmo.
UNCUTTABLE = ("points", "move axes")


class WorkPlane:
    """Wraps a polyscope slice plane. `plane` hands it out as an ordinary `geom.Plane`, so
    placement and the move constraints treat it like any other."""

    def __init__(self, slicer) -> None:
        self.slicer = slicer
        self.following = False
        self.cutting = False
        self.slicer.set_active(True)          # inactive planes lose their pose; see above
        self.slicer.set_draw_plane(True)
        self.slicer.set_draw_widget(True)
        self.slicer.set_transparency(TRANSPARENCY)
        self.slicer.set_grid_line_color(GRID_COLOR)
        self.set_pose((0.0, 0.0, 0.0), ps_up())

    @classmethod
    def attach(cls) -> "WorkPlane":
        return cls(ps.add_scene_slice_plane())

    @property
    def name(self) -> str:
        """Exemptions are per plane as well as per structure, so they need its name."""
        return self.slicer.get_name()

    @property
    def plane(self) -> Plane:
        """The pose as a constraint, read straight from polyscope."""
        return Plane(np.asarray(self.slicer.get_center(), dtype=float)[:3],
                     np.asarray(self.slicer.get_normal(), dtype=float)[:3])

    def set_pose(self, origin, normal) -> None:
        """Move the plane. A normal of any length works; a degenerate one is refused, so a
        half-typed number in the panel cannot destroy the plane."""
        normal = np.asarray(normal, dtype=float)
        length = float(np.linalg.norm(normal))
        for unit in filter(lambda _: length > 1e-9, [normal / length if length else normal]):
            self.slicer.set_pose(np.asarray(origin, dtype=float), unit)

    def follow(self, pivot, look_dir) -> None:
        """Lay the plane across the view at the pivot -- only while following."""
        for _ in filter(None, [self.following]):
            self.set_pose(pivot, look_dir)

    def apply(self, structures: dict) -> None:
        """Say which structures the plane may cut. Points and the gizmo never are; the rest
        only while `cutting`. Called after every sync, since structures are re-registered."""
        for name, structure in structures.items():
            structure.set_ignore_slice_plane(self.name, name in UNCUTTABLE or not self.cutting)

    def remove(self) -> None:
        self.slicer.remove()


def ps_up() -> np.ndarray:
    """The world up direction, as polyscope names it."""
    ups = {"x_up": (1.0, 0.0, 0.0), "neg_x_up": (-1.0, 0.0, 0.0),
           "y_up": (0.0, 1.0, 0.0), "neg_y_up": (0.0, -1.0, 0.0),
           "z_up": (0.0, 0.0, 1.0), "neg_z_up": (0.0, 0.0, -1.0)}
    return np.asarray(ups[ps.get_up_dir()], dtype=float)


def draw_settings(work_plane: Optional["WorkPlane"]) -> None:
    """Follow-or-stay, whether it cuts, and the numbers.

    The boxes are live only when the plane is not following the camera: while it follows,
    they are what the camera decided, and typing into them would be overwritten on the next
    frame. Everything else about the plane -- colour, transparency, dragging it by its
    widget -- is polyscope's own UI.
    """
    psim.TextUnformatted("Work plane")
    for plane in filter(None, [work_plane]):
        _, plane.following = psim.Checkbox("follow camera", plane.following)
        psim.SameLine()
        _, plane.cutting = psim.Checkbox("cut scene", plane.cutting)
        _draw_pose(plane)


def _draw_pose(work_plane: "WorkPlane") -> None:
    pose = work_plane.plane
    psim.BeginDisabled(work_plane.following)
    changed_origin, origin = psim.InputFloat3("origin", tuple(pose.origin))
    changed_normal, normal = psim.InputFloat3("normal", tuple(pose.normal))
    axis = _draw_orientations()
    psim.EndDisabled()
    for _ in filter(None, [changed_origin or changed_normal or axis is not None]):
        work_plane.set_pose(origin, ORIENTATIONS.get(axis, normal))


def _draw_orientations() -> Optional[str]:
    """One click for the three planes worth having a shortcut for."""
    pressed = [name for name in ORIENTATIONS if _small_button(name)]
    return next(iter(pressed), None)


def _small_button(name: str) -> bool:
    pressed = psim.SmallButton(name)
    psim.SameLine()
    return pressed
