"""Editor state and the operations the keymap dispatches.

The only state is an **ordered** selection and an optional live `Move`. Order is what
gives the user control over blockMesh vertex ordering, so the selection is a list, never a
set.

Everything here is polyscope-free except `handle_frame` and its helpers, which are the
single place mouse, keyboard and camera enter. The operations therefore stay testable
headlessly, and a future extrude can call `begin_move` on points it has just created.
"""

from typing import Optional

import numpy as np
import polyscope as ps
import polyscope.imgui as psim

from .. import storage
from ..document import Document
from ..geom import Axis, Plane
from ..transform import Move
from . import keymap, scene

LEFT_MOUSE = 0

# Axis letter -> direction. Plane constraints reuse it as the plane's *normal*, which is
# Blender's Shift+<axis> convention: 'everything except this axis'.
AXES = {"X": np.array([1.0, 0.0, 0.0]), "Y": np.array([0.0, 1.0, 0.0]), "Z": np.array([0.0, 0.0, 1.0])}

GROUND = Plane(np.zeros(3), np.array([0.0, 0.0, 1.0]))  # where a placed point lands by default

SURFACE_PREFIX = "surface::"  # how `scene` names a backdrop structure


class Editor:
    def __init__(self, document: Document, path: str = "untitled.shape") -> None:
        self.document = document
        self.path = path
        self.selection: list = []
        self.move: Optional[Move] = None
        self.snapping = False

    # ---------- selection ----------

    def select(self, point, additive: bool) -> None:
        self.selection = (self.selection if additive else [])[:]
        if point not in self.selection:
            self.selection.append(point)

    def clear_selection(self) -> None:
        self.selection = []

    # ---------- operations ----------

    def place_point(self, position) -> object:
        point = self.document.add_point(position)
        self.selection = [point]
        return point

    def make_block(self) -> Optional[object]:
        """Build a cell from the selection, in click order. A wrong count is a no-op: the
        selection is left intact so the user can keep clicking."""
        try:
            cell = self.document.add_cell(self.selection)
        except ValueError:
            return None
        self.clear_selection()
        return cell

    def delete(self) -> None:
        self.document.delete_points(self.selection)
        self.clear_selection()

    def save(self) -> None:
        storage.save(self.document, self.path)

    # ---------- the move modal ----------

    def begin_move(self, points=None, constraint=None, view_normal=None) -> None:
        """Start a move. Defaults to the selection, constrained to the plane through it
        facing the camera -- free move is not a special case, it is that plane."""
        points = self.selection if points is None else list(points)
        if not points:
            return
        self.move = Move.start(points, constraint or GROUND)
        self.move.constraint = constraint or Plane(self.move.centroid, np.asarray(view_normal, dtype=float))

    def constrain(self, axis: str, perpendicular: bool = False) -> None:
        """`X`/`Y`/`Z` for an axis, `perpendicular` for the plane that excludes it."""
        direction = AXES[axis]
        constraints = {False: Axis(self.move.centroid, direction), True: Plane(self.move.centroid, direction)}
        self.move.set_constraint(constraints[perpendicular])

    def solve(self, ray_origin, ray_direction, surface_hit=None) -> Optional[np.ndarray]:
        """Where the moved points should sit: the surface under the cursor projected back
        onto the constraint when snapping, else the constraint's own ray solution."""
        constraint = self.move.constraint
        if surface_hit is None:
            return constraint.from_ray(ray_origin, ray_direction)
        return constraint.project(surface_hit)

    def cancel_move(self) -> None:
        self.move.cancel()
        self.move = None

    def confirm_move(self) -> None:
        self.move.confirm()
        self.move = None

    # ---------- dispatch ----------

    def dispatch(self, action: str, view_normal=None) -> bool:
        """Run a keymap action by name; True when the scene must be re-synced."""
        actions = {
            "place_point": lambda: self.place_point(self._placement()),
            "move": lambda: self.begin_move(view_normal=view_normal),
            "make_block": self.make_block,
            "delete": self.delete,
            "save": self.save,
        }
        actions[action]()
        return True

    # ---------- the polyscope-facing part ----------

    def handle_frame(self) -> bool:
        """Mouse, keyboard and camera for one frame; True when the scene needs a resync.

        A live move owns the frame: the cursor drives it and a click confirms. Otherwise a
        click selects a point and the keymap dispatches.
        """
        if psim.GetIO().WantCaptureMouse:
            return False
        camera = ps.get_view_camera_parameters()
        return self._drive_move(camera) if self.move else self._idle(camera)

    def _drive_move(self, camera) -> bool:
        for axis in AXES:
            if psim.IsKeyPressed(getattr(psim, f"ImGuiKey_{axis}"), False):
                self.constrain(axis, perpendicular=psim.GetIO().KeyShift)
        self.snapping = psim.GetIO().KeyCtrl
        position = self.solve(*self._ray(camera), surface_hit=self._surface_hit())
        if position is not None:
            self.move.to(position)
        if psim.IsKeyPressed(psim.ImGuiKey_Escape, False):
            self.cancel_move()
        elif psim.IsMouseClicked(LEFT_MOUSE) or psim.IsKeyPressed(psim.ImGuiKey_Enter, False):
            self.confirm_move()
        return True

    def _idle(self, camera) -> bool:
        changed = False
        for binding in keymap.BINDINGS:
            if keymap.pressed(binding):
                changed |= self.dispatch(binding.action, view_normal=camera.get_look_dir())
        if psim.IsMouseClicked(LEFT_MOUSE):
            changed |= self._select_under_cursor()
        return changed

    def _select_under_cursor(self) -> bool:
        """Select the picked point. Polyscope reports the point cloud's hit index, which is
        the point's position in `document.points` -- the only place an index is legitimate,
        because it comes from the structure we just built."""
        result = ps.pick(screen_coords=psim.GetMousePos())
        if not result.is_hit or result.structure_name != scene.POINTS_NAME:
            return False
        self.select(self.document.points[result.structure_data["index"]], additive=psim.GetIO().KeyShift)
        return True

    def _ray(self, camera) -> tuple:
        origin = np.asarray(camera.get_position(), dtype=float)
        direction = np.asarray(ps.screen_coords_to_world_ray(psim.GetMousePos()), dtype=float)
        return origin, direction

    def _surface_hit(self, require_snapping: bool = True):
        """The world position of the surface under the cursor -- Polyscope's pick supplies
        it, so no proximity query. While moving it counts only with snapping held; when
        placing a point it always counts."""
        if require_snapping and not self.snapping:
            return None
        result = ps.pick(screen_coords=psim.GetMousePos())
        hit_a_surface = result.is_hit and result.structure_name.startswith(SURFACE_PREFIX)
        return np.asarray(result.position, dtype=float) if hit_a_surface else None

    def _placement(self) -> np.ndarray:
        """Where a new point lands: the surface under the cursor if one is there, else the
        ground plane."""
        hit = self._surface_hit(require_snapping=False)
        return GROUND.from_ray(*self._ray(ps.get_view_camera_parameters())) if hit is None else hit
