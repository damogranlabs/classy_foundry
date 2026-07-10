"""MappedSketch sketcher: viewport click-to-place/snap + points/quads tables.

The interaction rests on ps.pick (the world position on whatever structure is under the
cursor) and ImGui tables -- no scene-graph code, and **no work plane**: a sketch isn't
required to be planar, so a point is placed wherever the click lands on existing geometry
(the picker-of-everything — a reference point, a curve, an STL, another sketch). A reference
point (`PointStep`) snapshots its *exact* built position; anything else uses the raw pick
point. A click that hits nothing falls back to the world ground plane through the origin
(oriented by `up_dir`) via screen_coords_to_world_ray + camera position. Placements are
snapshots, not live refs, so the sketch keeps plain positions and transforms rigidly. Quad
corners are likewise picked by *world position* (depth-correct, so an off-plane vertex or an
overlay marker resolves to the right point).
"""

import numpy as np
import polyscope as ps
import polyscope.imgui as psim

from ..geom import ray_plane_hit
from ..steps.point import PointStep
from . import labels
from .widgets import vec_text

LEFT_MOUSE = 0

POINT_LABEL_COLOR = (0.75, 0.9, 1.0)   # point indices — light blue
BLOCK_LABEL_COLOR = (1.0, 0.85, 0.35)  # block (quad) indices — amber

# up_dir string -> the ground-plane normal it implies (the fallback placement plane's axis)
_UP_NORMALS = {
    "x_up": (1.0, 0.0, 0.0), "neg_x_up": (-1.0, 0.0, 0.0),
    "y_up": (0.0, 1.0, 0.0), "neg_y_up": (0.0, -1.0, 0.0),
    "z_up": (0.0, 0.0, 1.0), "neg_z_up": (0.0, 0.0, -1.0),
}


def _up_normal():
    return _UP_NORMALS.get(ps.get_up_dir(), (0.0, 0.0, 1.0))


def draw_number_labels(sketch, params=None):
    """Per-frame text overlay for the sketch being edited: the point index at each vertex and
    the block index at each quad centroid — so the tables' index-based editing (a quad is four
    point indices) reads directly off the viewport. Camera-dependent, so the app callback runs
    it every frame; a quad referencing an out-of-range point is skipped mid-edit. `params`
    resolves any parametric (`[bore/2, 0, 0]`) positions to where they actually render."""
    if not sketch.positions:
        return
    positions = np.asarray(sketch.resolved_positions(params), float).reshape(-1, 3)
    labels.draw_labels([(positions[i], str(i)) for i in range(len(positions))], POINT_LABEL_COLOR)
    labels.draw_labels([(positions[quad].mean(axis=0), str(i))
                        for i, quad in enumerate(sketch.quads) if quad and max(quad) < len(positions)],
                       BLOCK_LABEL_COLOR)

# The Points/Quads tables share a layout: a narrow index column, a *stretching* values column
# (the editable coordinates / corner indices), and a narrow delete column. Declaring this sizing
# is what stops ImGui's default equal-thirds — which starved the values while bloating the index.
INDEX_WIDTH = 26.0
DELETE_WIDTH = 24.0


class SketchEditor:
    def __init__(self):
        self.sketch = None
        self.mode = None        # None | "point" | "quad"
        self.pending = []       # point indices collected for the in-progress quad
        self.selected = None    # highlighted point index

    def activate(self, sketch):
        if sketch is self.sketch:
            return
        self.sketch, self.mode, self.pending, self.selected = sketch, None, [], None

    # ---------- viewport interaction ----------

    def handle_click(self, model):
        """Process a left click in the viewport; return True if anything changed.

        Point mode adds a point — snapshotting an existing reference point if the click
        landed on one, else a free point on the work plane; quad mode connects the *nearest
        existing point* (no new points), so quads are built by clicking roughly at corners.
        """
        if not self._armed():
            return False
        screen = psim.GetMousePos()
        if self.mode == "point":
            return self._place_point(screen, model)
        return self._extend_quad(screen, model)

    def _place_point(self, screen, model):
        """Add a point *onto whatever geometry is under the cursor* — the picker-of-everything:
        the depth-correct world position on any structure (reference point, curve, another
        sketch, an operation face, a Polyscope-sliced STL). A reference `Point` snapshots its
        *exact* built value (a sphere-surface pick is otherwise slightly off). A click that hits
        nothing falls to the world **ground plane through the origin** (oriented by `up_dir`);
        for anything off that plane, place a reference point / translate later. Snapshots, not
        live refs — the sketch stays a plain position list (rigid under transforms)."""
        result = ps.pick(screen_coords=screen)
        if result.is_hit:
            self._append(self._pick_position(result, model))
            return True
        hit = self._ground_hit(screen)
        if hit is None:
            return False
        self._append(list(hit))
        return True

    def _extend_quad(self, screen, model):
        """Add the clicked sketch vertex to the in-progress quad. Resolved by the pick's
        *world position* (depth-correct), not the work-plane intersection — so an off-plane
        on-curve point selects correctly instead of its plane-parallax neighbour, and an
        overlay marker (which sits exactly on its point) resolves to the right vertex. A
        click that hits nothing is ignored (no accidental neighbour)."""
        result = ps.pick(screen_coords=screen)
        if not result.is_hit:
            return False
        index = self._closest(np.asarray(result.position, float), model)
        if index is None:
            return False  # no existing points to connect
        self.pending.append(index)
        if len(self.pending) == 4:
            self.sketch.quads.append(list(self.pending))
            self.pending = []
        return True

    def _pick_position(self, result, model):
        """The world position a hit contributes: a reference point's (`PointStep`) *exact*
        built value — so an on-curve point snaps to its precise `curve.get_point(param)` — else
        the raw depth-correct pick position on whatever structure was hit."""
        step = model.step_by_name(result.structure_name.split("::")[0])
        if isinstance(step, PointStep):
            value = model.build().get(step)
            if value is not None:
                return list(np.asarray(value, float).ravel())
        return list(np.asarray(result.position, float).ravel())

    def _armed(self):
        return (self.sketch is not None and self.mode is not None
                and not psim.GetIO().WantCaptureMouse and psim.IsMouseClicked(LEFT_MOUSE))

    def _ground_hit(self, screen):
        """World point where the click ray meets the ground plane (through the origin, normal =
        `up_dir`) — the fallback surface when a click lands on no geometry."""
        camera = ps.get_view_camera_parameters()
        return ray_plane_hit(camera.get_position(), ps.screen_coords_to_world_ray(screen),
                             (0.0, 0.0, 0.0), _up_normal())

    def _closest(self, point, model):
        """Index of the existing point nearest to `point` (a picked world position), or None if
        there are none. Compares against *resolved* positions so a parametric vertex is matched
        where it actually renders."""
        positions = self.sketch.resolved_positions(model.build().params)
        if not positions:
            return None
        target = np.asarray(point)
        return min(range(len(positions)),
                   key=lambda i: float(np.linalg.norm(target - np.asarray(positions[i]))))

    def _append(self, hit):
        self.sketch.positions.append(list(hit))
        return len(self.sketch.positions) - 1

    # ---------- transient overlay ----------

    def render_overlay(self, context=None):
        """Re-add the transient markers after a rebuild. `context` carries the build's params so
        a parametric vertex's marker sits where it renders (None on the very first build)."""
        if self.sketch is None:
            return
        params = context.params if context is not None else None
        positions = self.sketch.resolved_positions(params)
        valid = len(positions)
        self._marker("::pending", [positions[i] for i in self.pending if i < valid], (1.0, 1.0, 0.0))
        chosen = [positions[self.selected]] if self._has_selection() else []
        self._marker("::selected", chosen, (1.0, 0.4, 0.0))

    def _has_selection(self):
        return self.selected is not None and self.selected < len(self.sketch.positions)

    def _marker(self, suffix, points, color):
        name = self.sketch.name + suffix
        if not points:
            ps.remove_point_cloud(name) if ps.has_point_cloud(name) else None
            return
        cloud = ps.register_point_cloud(name, np.asarray(points, float).reshape(-1, 3))
        cloud.set_color(color)
        cloud.set_radius(0.015, relative=False)

    # ---------- panel ----------

    def draw(self):
        """A Points section (Add point + table) and a Quads section (Add quad + table), each
        with its own add-mode toggle, then a trailing Done. Returns True if geometry changed."""
        dirty = self._section("Points", "Add point", "point", self._points_table)
        dirty |= self._section("Quads", f"Add quad ({len(self.pending)}/4)", "quad", self._quads_table)
        dirty |= self._mode_button("Done", None)  # leaves add-mode; sits below both tables
        return dirty

    def _section(self, header, add_label, mode, table):
        psim.TextUnformatted(header)
        dirty = self._mode_button(add_label, mode)
        return table() or dirty

    def _mode_button(self, label, mode):
        """A mode toggle rendered as a Selectable so the active add-mode stays highlighted;
        sized snug to its label (the Add-quad label carries a live `(n/4)` corner count)."""
        changed = False
        if psim.Selectable(label, self.mode == mode, size=(psim.CalcTextSize(label)[0] + 16.0, 0)):
            self.mode, self.pending = mode, []
            changed = True
        return changed

    def _begin_grid_table(self, name):
        """Begin a points/quads table with index|values|delete columns sized so the editable
        values column takes all the width the index and delete buttons don't need."""
        if not psim.BeginTable(name, 3):
            return False
        psim.TableSetupColumn("#", psim.ImGuiTableColumnFlags_WidthFixed, INDEX_WIDTH)
        psim.TableSetupColumn("values", psim.ImGuiTableColumnFlags_WidthStretch)
        psim.TableSetupColumn("x", psim.ImGuiTableColumnFlags_WidthFixed, DELETE_WIDTH)
        return True

    def _points_table(self):
        dirty = False
        delete = None
        if not self._begin_grid_table("points"):
            return False
        for i, position in enumerate(self.sketch.positions):
            psim.PushID(i)
            psim.TableNextRow()
            psim.TableNextColumn()
            if psim.Selectable(str(i), self.selected == i):
                self.selected = i
            psim.TableNextColumn()
            psim.SetNextItemWidth(-1)
            changed, new = psim.InputText("", vec_text(position))  # free text: `[bore/2, 0, 0]` ok
            if changed:
                self.sketch.positions[i] = new
                dirty = True
            psim.TableNextColumn()
            if psim.SmallButton("x"):
                delete = i
            psim.PopID()
        psim.EndTable()
        return self._delete_point(delete) or dirty

    def _delete_point(self, index):
        if index is None or self._referenced(index):
            return False
        self.sketch.positions.pop(index)
        self.sketch.quads[:] = [[c - (c > index) for c in quad] for quad in self.sketch.quads]
        self.selected = None
        self.pending = []  # indices shifted; abandon any in-progress quad
        return True

    def _referenced(self, index):
        return any(index in quad for quad in self.sketch.quads)

    def _quads_table(self):
        dirty = False
        delete = None
        if not self._begin_grid_table("quads"):
            return False
        for i, quad in enumerate(self.sketch.quads):
            psim.PushID(1000 + i)
            psim.TableNextRow()
            psim.TableNextColumn()
            psim.TextUnformatted(str(i))
            psim.TableNextColumn()
            psim.SetNextItemWidth(-1)
            changed, new = psim.InputInt4("", quad)
            if changed:
                self.sketch.quads[i] = list(new)
                dirty = True
            psim.TableNextColumn()
            if psim.SmallButton("x"):
                delete = i
            psim.PopID()
        psim.EndTable()
        if delete is not None:
            self.sketch.quads.pop(delete)
            dirty = True
        return dirty
