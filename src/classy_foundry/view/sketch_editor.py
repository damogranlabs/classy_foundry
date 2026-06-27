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

LEFT_MOUSE = 0


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
        """Mode buttons + points/quads tables; return True if geometry changed."""
        dirty = self._mode_buttons()
        dirty |= self._points_table()
        dirty |= self._quads_table()
        return dirty

    def _mode_buttons(self):
        changed = False
        for label, mode in (("Add point", "point"), ("Add quad", "quad"), ("Done", None)):
            highlighted = self.mode == mode
            if psim.Selectable(label, highlighted, size=(70, 0)):
                self.mode, self.pending = mode, []
                changed = True
            psim.SameLine()
        psim.TextUnformatted(f"  ({len(self.pending)}/4)" if self.mode == "quad" else "")
        return changed

    def _points_table(self):
        dirty = False
        delete = None
        psim.TextUnformatted("Points")
        if not psim.BeginTable("points", 3):
            return False
        for i, position in enumerate(self.sketch.positions):
            psim.PushID(i)
            psim.TableNextRow()
            psim.TableNextColumn()
            if psim.Selectable(str(i), self.selected == i):
                self.selected = i
            psim.TableNextColumn()
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
        psim.TextUnformatted("Quads")
        if not psim.BeginTable("quads", 3):
            return False
        for i, quad in enumerate(self.sketch.quads):
            psim.PushID(1000 + i)
            psim.TableNextRow()
            psim.TableNextColumn()
            psim.TextUnformatted(str(i))
            psim.TableNextColumn()
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
