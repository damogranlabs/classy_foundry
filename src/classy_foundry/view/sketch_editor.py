"""MappedSketch sketcher: viewport click-to-place/snap + points/quads tables.

The interaction rests on screen_coords_to_world_ray + camera position (drop a free point on
the work plane), ps.pick (resolve an existing vertex by its world position), and ImGui
tables -- no scene-graph code. Quad corners are picked by *world position* (depth-correct, so
off-plane on-curve points select correctly and overlay markers resolve to their vertex), not
by work-plane proximity. Placing a point is pick-based for reuse: a click on a reference
point (`PointStep`) stores a *reference* to it (the sketch vertex is that named point, so the
sketch follows it and codegen names it, like a `Face` corner); a click that misses every
reference point drops a free coordinate on the work plane. A stored entry is therefore a
`PointStep` *or* an `[x, y, z]`, so every place the sketcher reads vertex coordinates goes
through `sketch.resolved_positions(context)` (a ref → its built coordinate, a literal
through); a ref can be *frozen* to a plain coordinate in the points table for the rigid-
transform + clamp workflow.
"""

import numpy as np
import polyscope as ps
import polyscope.imgui as psim

from ..geom import ray_plane_hit
from ..steps.point import PointStep
from . import labels
from .display import POINT_RADIUS

LEFT_MOUSE = 0

# Pending/selected markers sit on the sketch points, so they're sized *relative* to the scene
# (like every other radius) — a bit larger than the base point so the highlight envelops it. An
# absolute radius here made them swallow a small model (blade-scale) and never rescale.
MARKER_RADIUS = 1.5 * POINT_RADIUS

POINT_LABEL_COLOR = (0.75, 0.9, 1.0)   # point indices — light blue
BLOCK_LABEL_COLOR = (1.0, 0.85, 0.35)  # block (quad) indices — amber


def draw_number_labels(sketch, context):
    """Per-frame text overlay for the sketch being edited: the point index at each vertex and
    the block index at each quad centroid — so the tables' index-based editing (a quad is four
    point indices) reads directly off the viewport. Camera-dependent, so the app callback runs
    it every frame. Vertex coordinates come from `resolved_positions` (an entry may be a point
    ref); a vertex whose ref hasn't built (None), and a quad touching one, are skipped."""
    coords = sketch.resolved_positions(context)
    labels.draw_labels([(c, str(i)) for i, c in enumerate(coords) if c is not None], POINT_LABEL_COLOR)
    labels.draw_labels([(np.asarray([coords[c] for c in quad], float).mean(axis=0), str(i))
                        for i, quad in enumerate(sketch.quads)
                        if quad and max(quad) < len(coords) and all(coords[c] is not None for c in quad)],
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

        Point mode adds a point — a *reference* to the reference point the click hit, else a
        free coordinate on the work plane; quad mode connects the *nearest existing vertex* (no
        new points), so quads are built by clicking roughly at corners.
        """
        if not self._armed():
            return False
        screen = psim.GetMousePos()
        if self.mode == "point":
            return self._place_point(screen, model)
        return self._extend_quad(screen, model.build())

    def _place_point(self, screen, model):
        """Add a point: store a *reference* to the reference point the click hit (the sketch
        vertex follows that named point and codegen names it), else drop a free coordinate on
        the work plane."""
        ref = self._picked_reference(screen, model)
        if ref is not None:
            self._append(ref)
            return True
        hit = self._plane_hit(screen)
        if hit is None:
            return False
        self._append(list(hit))
        return True

    def _extend_quad(self, screen, context):
        """Add the clicked sketch vertex to the in-progress quad. Resolved by the pick's
        *world position* (depth-correct), not the work-plane intersection — so an off-plane
        on-curve point selects correctly instead of its plane-parallax neighbour, and an
        overlay marker (which sits exactly on its point) resolves to the right vertex. A
        click that hits nothing is ignored (no accidental neighbour)."""
        result = ps.pick(screen_coords=screen)
        if not result.is_hit:
            return False
        index = self._closest(np.asarray(result.position, float), context)
        if index is None:
            return False  # no existing points to connect
        self.pending.append(index)
        if len(self.pending) == 4:
            self.sketch.quads.append(list(self.pending))
            self.pending = []
        return True

    def _picked_reference(self, screen, model):
        """The reference-point step (`PointStep`) under the click, or None if the click missed
        every reference point. The step itself is stored (a live ref), resolved to coordinates
        only for display/build."""
        result = ps.pick(screen_coords=screen)
        if not result.is_hit:
            return None
        step = model.step_by_name(result.structure_name.split("::")[0])
        return step if isinstance(step, PointStep) else None

    def _armed(self):
        return (self.sketch is not None and self.mode is not None
                and not psim.GetIO().WantCaptureMouse and psim.IsMouseClicked(LEFT_MOUSE))

    def _plane_hit(self, screen):
        """World point where the click ray meets the sketch plane, or None."""
        camera = ps.get_view_camera_parameters()
        return ray_plane_hit(camera.get_position(), ps.screen_coords_to_world_ray(screen),
                             self.sketch.work_origin, self.sketch.work_normal)

    def _closest(self, point, context):
        """Index of the existing vertex nearest `point`, resolving ref entries via `context` and
        skipping any that haven't built; None if there is nothing resolvable to connect."""
        coords = self.sketch.resolved_positions(context)
        candidates = [(i, np.asarray(c)) for i, c in enumerate(coords) if c is not None]
        if not candidates:
            return None
        target = np.asarray(point)
        return min(candidates, key=lambda ic: float(np.linalg.norm(target - ic[1])))[0]

    def _append(self, entry):
        """Append a stored vertex — a `PointStep` reference or an `[x, y, z]` literal, kept as-is."""
        self.sketch.positions.append(entry)
        return len(self.sketch.positions) - 1

    # ---------- transient overlay ----------

    def render_overlay(self, context):
        if self.sketch is None:
            return
        coords = self.sketch.resolved_positions(context)  # ref vertices -> coordinates
        pending = [coords[i] for i in self.pending if i < len(coords) and coords[i] is not None]
        self._marker("::pending", pending, (1.0, 1.0, 0.0))
        selected = coords[self.selected] if self._has_selection() else None
        self._marker("::selected", [selected] if selected is not None else [], (1.0, 0.4, 0.0))

    def _has_selection(self):
        return self.selected is not None and self.selected < len(self.sketch.positions)

    def _marker(self, suffix, points, color):
        name = self.sketch.name + suffix
        if not points:
            ps.remove_point_cloud(name) if ps.has_point_cloud(name) else None
            return
        cloud = ps.register_point_cloud(name, np.asarray(points, float).reshape(-1, 3))
        cloud.set_color(color)
        cloud.set_radius(MARKER_RADIUS)  # relative -> scales with the model, like the base points

    # ---------- panel ----------

    def draw(self, context):
        """A Points section (Add point + table) and a Quads section (Add quad + table), each
        with its own add-mode toggle, then a trailing Done. Returns True if geometry changed.
        `context` resolves ref-valued vertices for the points table (name + freeze)."""
        dirty = self._section("Points", "Add point", "point", lambda: self._points_table(context))
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

    def _points_table(self, context):
        dirty = False
        delete = None
        if not self._begin_grid_table("points"):
            return False
        coords = self.sketch.resolved_positions(context)
        for i, entry in enumerate(self.sketch.positions):
            psim.PushID(i)
            psim.TableNextRow()
            psim.TableNextColumn()
            if psim.Selectable(str(i), self.selected == i):
                self.selected = i
            psim.TableNextColumn()
            dirty |= self._point_cell(i, entry, coords[i])  # a referenced point, or editable xyz
            psim.TableNextColumn()
            if psim.SmallButton("x"):
                delete = i
            psim.PopID()
        psim.EndTable()
        return self._delete_point(delete) or dirty

    def _point_cell(self, i, entry, coord):
        """The values cell of one point row: a *referenced* vertex shows its point name plus a
        'freeze' button (replace the reference with its current coordinate — the rigid-transform +
        clamp workflow); a literal vertex shows editable xyz. Returns True if it changed."""
        if isinstance(entry, PointStep):
            psim.TextUnformatted(entry.name)
            psim.SameLine()
            if psim.SmallButton("freeze") and coord is not None:
                self.sketch.positions[i] = list(coord)
                return True
            return False
        psim.SetNextItemWidth(-1)
        changed, new = psim.InputFloat3("", entry)
        if changed:
            self.sketch.positions[i] = list(new)
        return changed

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
