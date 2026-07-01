"""MappedSketch sketcher: viewport click-to-place/snap + points/quads tables.

The interaction rests on screen_coords_to_world_ray + camera position (drop a free point on
the work plane), ps.pick (resolve an existing vertex by its world position), and ImGui
tables -- no scene-graph code. Quad corners are picked by *world position* (depth-correct, so
off-plane on-curve points select correctly and overlay markers resolve to their vertex), not
by work-plane proximity. Placing a point is pick-based for reuse: a click on a reference
point (`PointStep`) snapshots that point's exact position into the sketch (the sketch keeps
plain positions, so it transforms rigidly — the curve binding lives in the clamp, not here);
a click that misses every reference point drops a free point on the work plane.
"""

import numpy as np
import polyscope as ps
import polyscope.imgui as psim

from ..geom import ray_plane_hit
from ..steps.point import PointStep
from . import labels

LEFT_MOUSE = 0

POINT_LABEL_COLOR = (0.75, 0.9, 1.0)   # point indices — light blue
BLOCK_LABEL_COLOR = (1.0, 0.85, 0.35)  # block (quad) indices — amber


def draw_number_labels(sketch):
    """Per-frame text overlay for the sketch being edited: the point index at each vertex and
    the block index at each quad centroid — so the tables' index-based editing (a quad is four
    point indices) reads directly off the viewport. Camera-dependent, so the app callback runs
    it every frame; a quad referencing an out-of-range point is skipped mid-edit."""
    if not sketch.positions:
        return
    positions = np.asarray(sketch.positions, float).reshape(-1, 3)
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
        return self._extend_quad(screen)

    def _place_point(self, screen, model):
        """Add a point: snapshot a reference point if the click hit one, else drop a free
        point on the work plane. (Snapshot, not a live ref — the sketch stays a plain
        position list so transforms stay rigid; the curve binding lives in the clamp.)"""
        ref = self._picked_reference_position(screen, model)
        if ref is not None:
            self._append(ref)
            return True
        hit = self._plane_hit(screen)
        if hit is None:
            return False
        self._append(list(hit))
        return True

    def _extend_quad(self, screen):
        """Add the clicked sketch vertex to the in-progress quad. Resolved by the pick's
        *world position* (depth-correct), not the work-plane intersection — so an off-plane
        on-curve point selects correctly instead of its plane-parallax neighbour, and an
        overlay marker (which sits exactly on its point) resolves to the right vertex. A
        click that hits nothing is ignored (no accidental neighbour)."""
        result = ps.pick(screen_coords=screen)
        if not result.is_hit:
            return False
        index = self._closest(np.asarray(result.position, float))
        if index is None:
            return False  # no existing points to connect
        self.pending.append(index)
        if len(self.pending) == 4:
            self.sketch.quads.append(list(self.pending))
            self.pending = []
        return True

    def _picked_reference_position(self, screen, model):
        """Exact world position of a reference point (`PointStep`) under the click, or None
        if the click missed every reference point. Resolves the picked step's built value, so
        an on-curve point snaps to its precise `curve.get_point(param)`."""
        result = ps.pick(screen_coords=screen)
        if not result.is_hit:
            return None
        step = model.step_by_name(result.structure_name.split("::")[0])
        if not isinstance(step, PointStep):
            return None
        value = model.build().get(step)
        return None if value is None else list(np.asarray(value, float).ravel())

    def _armed(self):
        return (self.sketch is not None and self.mode is not None
                and not psim.GetIO().WantCaptureMouse and psim.IsMouseClicked(LEFT_MOUSE))

    def _plane_hit(self, screen):
        """World point where the click ray meets the sketch plane, or None."""
        camera = ps.get_view_camera_parameters()
        return ray_plane_hit(camera.get_position(), ps.screen_coords_to_world_ray(screen),
                             self.sketch.work_origin, self.sketch.work_normal)

    def _closest(self, point):
        """Index of the existing point nearest to `point`, or None if there are none."""
        if not self.sketch.positions:
            return None
        target = np.asarray(point)
        return min(range(len(self.sketch.positions)),
                   key=lambda i: float(np.linalg.norm(target - np.asarray(self.sketch.positions[i]))))

    def _append(self, hit):
        self.sketch.positions.append(list(hit))
        return len(self.sketch.positions) - 1

    # ---------- transient overlay ----------

    def render_overlay(self):
        if self.sketch is None:
            return
        valid = len(self.sketch.positions)
        self._marker("::pending", [self.sketch.positions[i] for i in self.pending if i < valid], (1.0, 1.0, 0.0))
        chosen = [self.sketch.positions[self.selected]] if self._has_selection() else []
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
            changed, new = psim.InputFloat3("", position)
            if changed:
                self.sketch.positions[i] = list(new)
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
