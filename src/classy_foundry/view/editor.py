"""Editor state and the operations the keymap dispatches.

The only state is an **ordered** selection and an optional live `Move`. Order is what
gives the user control over blockMesh vertex ordering, so the selection is a list, never a
set.

Everything here is polyscope-free except `handle_frame` and its helpers, which are the
single place mouse, keyboard and camera enter. The operations therefore stay testable
headlessly, and a future extrude can call `begin_move` on points it has just created.
"""

import os
from typing import Optional

import numpy as np
import polyscope as ps
import polyscope.imgui as psim

from .. import storage
from ..document import Document
from ..geom import Axis, FreePlane, Plane, load_trimesh, surface_hit
from ..transform import Move
from . import keymap, scene

LEFT_MOUSE = 0

# Axis letter -> direction. Plane constraints reuse it as the plane's *normal*, which is
# Blender's Shift+<axis> convention: 'everything except this axis'.
AXES = {"X": np.array([1.0, 0.0, 0.0]), "Y": np.array([0.0, 1.0, 0.0]), "Z": np.array([0.0, 0.0, 1.0])}

GROUND = Plane(np.zeros(3), np.array([0.0, 0.0, 1.0]))  # where a placed point lands by default


def _toggled(selection: list, item, additive: bool) -> list:
    """The selection after clicking `item`. A plain click starts fresh with it; a Shift
    click adds it, or removes it again if it was already there. Order is preserved, since
    click order is what decides a block's vertex ordering."""
    kept = list(selection) if additive else []
    return [other for other in kept if other is not item] if item in kept else kept + [item]


class Editor:
    def __init__(self, document: Document, path: str = "untitled.shape", work_plane=None) -> None:
        self.document = document
        self.work_plane = work_plane
        self.path = path
        self.selection: list = []
        self.cells: list = []
        self.move: Optional[Move] = None
        self.snapping = False
        # Points created *for* the live move (by `duplicate`). Cancelling discards them, so
        # an abandoned copy never stays stacked on its original. Empty for a plain move,
        # which is why cancelling one deletes nothing without asking whether it should.
        self.born: list = []

    # ---------- selection ----------

    def select(self, point, additive: bool) -> None:
        self.cells = self.cells if additive else []
        self.selection = _toggled(self.selection, point, additive)

    def select_cell(self, cell, additive: bool) -> None:
        """Blocks and points share the click: a plain click starts a fresh selection of
        either kind, Shift adds to whatever is already there -- or removes it again."""
        self.selection = self.selection if additive else []
        self.cells = _toggled(self.cells, cell, additive)

    def select_nothing(self, additive: bool) -> None:
        """A click that hit nothing. Without Shift that means 'start over'; with it, it was
        a slip of the hand and the selection stands."""
        self.clear_selection() if not additive else None

    def clear_selection(self) -> None:
        self.selection = []
        self.cells = []

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

    def duplicate(self, view_normal=None) -> None:
        """Copy the selection and grab the copies straight away.

        Placing every point from scratch means starting from wherever the ground plane is,
        which is never where it should be; copying a point that is already right and
        nudging it is far less work. The copies are never left where the originals are:
        confirming has moved them, and cancelling deletes them."""
        copies = [self.document.add_point(np.array(point.position)) for point in self.selection]
        self.selection, self.born = copies, copies
        self.begin_move(points=copies, view_normal=view_normal)

    def delete(self) -> None:
        """Selected blocks go; selected points go and take their blocks with them. A block
        is topology, so deleting one leaves the points it was built on -- they are usually
        wanted for whatever replaces it."""
        self.document.delete_cells(self.cells)
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
        self.move.constraint = constraint or FreePlane(self.move.centroid,
                                                      np.asarray(view_normal, dtype=float))

    def constrain_to_work_plane(self) -> None:
        """Constrain the live move to the work plane itself -- not to a plane through the
        selection, as `X`/`Y`/`Z` do: the point is meant to *land on* it. Snapping then
        traces where that plane cuts the reference surface."""
        self.move.set_constraint(self.placement_plane)

    def constrain(self, axis: str, perpendicular: bool = False) -> None:
        """`X`/`Y`/`Z` for an axis, `perpendicular` for the plane that excludes it."""
        direction = AXES[axis]
        constraints = {False: Axis(self.move.centroid, direction), True: Plane(self.move.centroid, direction)}
        self.move.set_constraint(constraints[perpendicular])

    def solve(self, ray_origin, ray_direction, snapping: bool = False) -> Optional[np.ndarray]:
        """Where the moved points should sit.

        Snapping asks the constraint what it means by the surface: a free move follows the
        surface itself, a plane traces the cross-section it cuts, an axis takes the surface
        point pulled back onto the axis. A snap that finds nothing (the cursor is off the
        geometry, or the plane misses it) falls back to the ordinary ray solution, so the
        point keeps following the mouse instead of freezing."""
        constraint = self.move.constraint
        snapped = constraint.snap(ray_origin, ray_direction, self.surfaces()) if snapping else None
        return constraint.from_ray(ray_origin, ray_direction) if snapped is None else snapped

    def surfaces(self) -> list:
        """The reference meshes currently loaded -- what snapping runs against.
        `load_trimesh` memoises, so this is a dictionary lookup per frame."""
        return [load_trimesh(patch.surface) for patch in self.document.patches
                if patch.surface and os.path.exists(patch.surface)]

    def cancel_move(self) -> None:
        """Put the moved points back -- and discard any that exist only because of this
        move (`self.born`), which for an ordinary move is none of them."""
        self.move.cancel()
        self.move = None
        discarded = frozenset(self.born)
        self.document.delete_points(self.born)
        self.selection = [point for point in self.selection if point not in discarded]
        self.born = []

    def confirm_move(self) -> None:
        self.move.confirm()
        self.move = None
        self.born = []

    # ---------- dispatch ----------

    def dispatch(self, action: str, view_normal=None) -> bool:
        """Run a keymap action by name; True when the scene must be re-synced."""
        actions = {
            "place_point": lambda: self.place_point(self._placement()),
            "move": lambda: self.begin_move(view_normal=view_normal),
            "duplicate": lambda: self.duplicate(view_normal=view_normal),
            "make_block": self.make_block,
            "delete": self.delete,
            "deselect": self.clear_selection,
            "work_plane": self._toggle_follow,
            "save": self.save,
        }
        actions[action]()
        return True

    def _toggle_follow(self) -> None:
        """`W` when idle: let the work plane ride the camera, or leave it where it is.
        Following is for aiming; locked is for placing several points on one plane."""
        for work_plane in filter(None, [self.work_plane]):
            work_plane.following = not work_plane.following

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
        for _ in filter(None, [psim.IsKeyPressed(psim.ImGuiKey_W, False)]):
            self.constrain_to_work_plane()
        self.snapping = psim.GetIO().KeyCtrl
        position = self.solve(*self._ray(camera), snapping=self.snapping)
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
        """Select whatever was clicked: a point, or the block a clicked face belongs to.

        Polyscope reports the hit structure and the index of the element within it, which
        is the only place an index is legitimate -- it addresses the structure we just
        built, not the document. Points are drawn on top, so a click near one takes the
        point and a click elsewhere on a block takes the block."""
        result = ps.pick(screen_coords=psim.GetMousePos())
        pickers = {
            scene.POINTS_NAME: lambda index: self.select(self.document.points[index],
                                                         additive=psim.GetIO().KeyShift),
            scene.CELLS_NAME: lambda index: self.select_cell(
                scene.cell_owners(self.document.cells)[index], additive=psim.GetIO().KeyShift),
        }
        additive = psim.GetIO().KeyShift
        picker = pickers.get(result.structure_name) if result.is_hit else None
        for pick in filter(None, [picker]):
            pick(result.structure_data["index"])
            return True
        self.select_nothing(additive)
        return True

    def _ray(self, camera) -> tuple:
        origin = np.asarray(camera.get_position(), dtype=float)
        direction = np.asarray(ps.screen_coords_to_world_ray(psim.GetMousePos()), dtype=float)
        return origin, direction

    def _placement(self) -> np.ndarray:
        """Where a new point lands: on the reference surface under the cursor if there is
        one, else on the **work plane** -- which is where knowing the depth in advance comes
        from. Without a work plane (headless, tests) the ground serves."""
        ray = self._ray(ps.get_view_camera_parameters())
        hit = surface_hit(*ray, self.surfaces())
        return self.placement_plane.from_ray(*ray) if hit is None else hit

    @property
    def placement_plane(self) -> Plane:
        for work_plane in filter(None, [self.work_plane]):
            return work_plane.plane
        return GROUND
