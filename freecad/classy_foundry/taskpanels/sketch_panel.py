"""Task panel for editing a MappedSketch: point placement + quad definition."""

import numpy as np
from pivy import coin
from PySide import QtCore, QtGui

import FreeCAD
import FreeCADGui

CLAMP_TYPES = ["Free", "Fixed", "OnCurve", "OnSurface"]
SNAP_PIXELS = 15

_NORMAL_PRESETS = [
    ("XY", (0.0, 0.0, 1.0)),
    ("XZ", (0.0, 1.0, 0.0)),
    ("YZ", (1.0, 0.0, 0.0)),
]

_PREF_VIEW = "User parameter:BaseApp/Preferences/View"


def _pref_color(key, default):
    """Read an RGBA uint32 pref from BaseApp/Preferences/View → (r, g, b) floats."""
    try:
        val = FreeCAD.ParamGet(_PREF_VIEW).GetUnsigned(key, 0)
        if val == 0:
            return default
        return ((val >> 24) & 0xFF) / 255.0, ((val >> 16) & 0xFF) / 255.0, ((val >> 8) & 0xFF) / 255.0
    except Exception:
        return default


def _make_point(pos):
    return {"pos": list(pos), "clamp": "Free", "curve_idx": None, "relational": None}


def _point_in_quad(cursor, pts, normal):
    """True if cursor lies inside the quad defined by pts[0..3] on the plane with given normal."""
    n = np.array(normal, dtype=float)
    signs = [np.dot(np.cross(pts[(j + 1) % 4] - pts[j], cursor - pts[j]), n) for j in range(4)]
    return all(s >= 0 for s in signs) or all(s <= 0 for s in signs)


def _ray_plane_intersect(ray_point, ray_dir, plane_origin, plane_normal):
    """Intersect a ray with a plane; falls back to normal projection if ray is parallel."""
    n = np.array(plane_normal, dtype=float)
    nn = np.linalg.norm(n)
    n = np.array([0.0, 0.0, 1.0]) if nn < 1e-10 else n / nn

    d = np.array(ray_dir, dtype=float)
    dn = np.linalg.norm(d)
    d = d / dn if dn > 1e-10 else -n

    p = np.array(ray_point, dtype=float)
    o = np.array(plane_origin, dtype=float)

    denom = np.dot(d, n)
    if abs(denom) < 1e-10:
        return (p - np.dot(p - o, n) * n).tolist()

    t = np.dot(o - p, n) / denom
    return (p + t * d).tolist()


class SketchTaskPanel:
    def __init__(self, obj):
        self.obj = obj
        self._points = [dict(p) for p in obj.SketchPoints]
        self._quads = [list(q) for q in obj.SketchQuads]
        chops = getattr(obj, "SketchChops", None) or [[], []]
        self._chops = [set(chops[0]), set(chops[1])]
        self._mode = None
        self._quad_in_progress = []
        self._hovered_idx = -1
        self._selected_idx = -1
        self._hovered_quad_idx = -1
        self._selected_quad_idx = -1
        self._dragging = False
        self._drag_idx = -1

        self._build_ui()
        self._init_work_plane_ui()
        self._setup_coin3d()

        view = FreeCADGui.ActiveDocument.ActiveView
        self._event_cb = view.addEventCallbackPivy(
            coin.SoMouseButtonEvent.getClassTypeId(), self._on_mouse_click
        )
        self._move_cb = view.addEventCallbackPivy(
            coin.SoLocation2Event.getClassTypeId(), self._on_mouse_move
        )

        self._rebuild_tables()
        self._rebuild_coin3d()
        self._align_camera_to_plane()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self.form = QtGui.QWidget()
        self.form.setWindowTitle("Sketch Editor")
        layout = QtGui.QVBoxLayout(self.form)

        # Work plane section
        wp_row = QtGui.QHBoxLayout()
        wp_row.addWidget(QtGui.QLabel("<b>Work Plane</b>"))
        self._normal_btns = []
        self._normal_btn_group = QtGui.QButtonGroup()
        self._normal_btn_group.setExclusive(True)
        for i, (label, _) in enumerate(_NORMAL_PRESETS):
            btn = QtGui.QPushButton(label)
            btn.setCheckable(True)
            self._normal_btn_group.addButton(btn, i)
            self._normal_btns.append(btn)
            wp_row.addWidget(btn)
        wp_row.addStretch()
        layout.addLayout(wp_row)

        # Points section
        layout.addWidget(QtGui.QLabel("<b>Points</b>"))
        pts_btns = QtGui.QHBoxLayout()
        self._add_pt_btn = QtGui.QPushButton("+")
        self._add_pt_btn.setToolTip("Toggle: click in viewport to place points")
        self._add_pt_btn.setCheckable(True)
        self._del_pt_btn = QtGui.QPushButton("−")
        self._del_pt_btn.setToolTip("Toggle: click a row to delete that point")
        self._del_pt_btn.setCheckable(True)
        pts_btns.addWidget(self._add_pt_btn)
        pts_btns.addWidget(self._del_pt_btn)
        pts_btns.addStretch()
        layout.addLayout(pts_btns)

        self._pts_table = QtGui.QTableWidget(0, 5)
        self._pts_table.setHorizontalHeaderLabels(["#", "X", "Y", "Z", "Clamp"])
        self._pts_table.horizontalHeader().setStretchLastSection(True)
        self._pts_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        layout.addWidget(self._pts_table)

        # Quads section
        layout.addWidget(QtGui.QLabel("<b>Quads</b>"))
        quad_btns = QtGui.QHBoxLayout()
        self._add_quad_btn = QtGui.QPushButton("+")
        self._add_quad_btn.setToolTip("Toggle: click 4 points in viewport to define quads")
        self._add_quad_btn.setCheckable(True)
        self._del_quad_btn = QtGui.QPushButton("−")
        self._del_quad_btn.setToolTip("Toggle: click a row to delete that quad")
        self._del_quad_btn.setCheckable(True)
        quad_btns.addWidget(self._add_quad_btn)
        quad_btns.addWidget(self._del_quad_btn)
        quad_btns.addStretch()
        layout.addLayout(quad_btns)

        self._quads_table = QtGui.QTableWidget(0, 7)
        self._quads_table.setHorizontalHeaderLabels(["#", "P0", "P1", "P2", "P3", "Chop 0", "Chop 1"])
        self._quads_table.horizontalHeader().setStretchLastSection(True)
        self._quads_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        layout.addWidget(self._quads_table)

        self._status = QtGui.QLabel("")
        layout.addWidget(self._status)

        for i, btn in enumerate(self._normal_btns):
            btn.clicked.connect(lambda _checked, idx=i: self._on_normal_preset(idx))
        self._add_pt_btn.clicked.connect(self._toggle_add_point)
        self._del_pt_btn.clicked.connect(self._toggle_delete_point)
        self._add_quad_btn.clicked.connect(self._toggle_add_quad)
        self._del_quad_btn.clicked.connect(self._toggle_delete_quad)
        self._pts_table.cellChanged.connect(self._on_point_cell_changed)
        self._pts_table.itemSelectionChanged.connect(self._on_point_selection_changed)
        self._pts_table.itemClicked.connect(self._on_pt_table_item_clicked)
        self._quads_table.cellChanged.connect(self._on_quad_cell_changed)
        self._quads_table.itemSelectionChanged.connect(self._on_quad_selection_changed)
        self._quads_table.itemClicked.connect(self._on_quad_table_item_clicked)

    # ------------------------------------------------------------------ Coin3D

    def _setup_coin3d(self):
        self._root = coin.SoSeparator()

        self._vertex_color    = _pref_color("SketchVertexColor", (0.2, 0.2, 0.8))
        self._highlight_color = _pref_color("HighlightColor",   (0.0, 0.78, 0.0))
        self._selection_color = _pref_color("SelectionColor",   (0.11, 0.58, 1.0))
        self._edge_color      = _pref_color("SketchEdgeColor",  (0.2, 0.2, 0.8))
        edited_color          = _pref_color("EditedEdgeColor",  (1.0, 0.7, 0.0))

        # Points — per-vertex material so hover/selection can be coloured individually
        pt_sep = coin.SoSeparator()
        pt_binding = coin.SoMaterialBinding()
        pt_binding.value = coin.SoMaterialBinding.PER_VERTEX
        self._pt_material = coin.SoMaterial()
        self._pt_coords = coin.SoCoordinate3()
        pt_markers = coin.SoMarkerSet()
        pt_markers.markerIndex.setValue(coin.SoMarkerSet.CIRCLE_FILLED_9_9)
        pt_sep.addChild(pt_binding)
        pt_sep.addChild(self._pt_material)
        pt_sep.addChild(self._pt_coords)
        pt_sep.addChild(pt_markers)
        self._root.addChild(pt_sep)

        # In-progress quad corner markers
        prog_sep = coin.SoSeparator()
        prog_col = coin.SoBaseColor()
        prog_col.rgb = edited_color
        self._prog_coords = coin.SoCoordinate3()
        prog_markers = coin.SoMarkerSet()
        prog_markers.markerIndex.setValue(coin.SoMarkerSet.CIRCLE_FILLED_9_9)
        prog_sep.addChild(prog_col)
        prog_sep.addChild(self._prog_coords)
        prog_sep.addChild(prog_markers)
        self._root.addChild(prog_sep)

        # Quad filled faces — per-face material for hover/selection colour
        face_sep = coin.SoSeparator()
        face_hints = coin.SoShapeHints()
        face_hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE
        face_binding = coin.SoMaterialBinding()
        face_binding.value = coin.SoMaterialBinding.PER_FACE
        self._face_material = coin.SoMaterial()
        self._face_coords = coin.SoCoordinate3()
        self._face_set = coin.SoIndexedFaceSet()
        face_sep.addChild(face_hints)
        face_sep.addChild(face_binding)
        face_sep.addChild(self._face_material)
        face_sep.addChild(self._face_coords)
        face_sep.addChild(self._face_set)
        self._root.addChild(face_sep)

        # Quad edge lines on top (single uniform colour)
        edge_sep = coin.SoSeparator()
        edge_col = coin.SoBaseColor()
        edge_col.rgb = self._edge_color
        edge_style = coin.SoDrawStyle()
        edge_style.lineWidth = 2.0
        self._edge_coords = coin.SoCoordinate3()
        self._edge_lines = coin.SoIndexedLineSet()
        edge_sep.addChild(edge_col)
        edge_sep.addChild(edge_style)
        edge_sep.addChild(self._edge_coords)
        edge_sep.addChild(self._edge_lines)
        self._root.addChild(edge_sep)

        FreeCADGui.ActiveDocument.ActiveView.getSceneGraph().addChild(self._root)

    # ------------------------------------------------------------------ Work plane

    def _init_work_plane_ui(self):
        n = self.obj.WorkNormal
        current = (round(n.x, 6), round(n.y, 6), round(n.z, 6))
        for btn, (_, vec) in zip(self._normal_btns, _NORMAL_PRESETS):
            btn.setChecked(current == vec)

    def _align_camera_to_plane(self):
        n = self.obj.WorkNormal
        view = FreeCADGui.ActiveDocument.ActiveView
        rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), FreeCAD.Vector(n.x, n.y, n.z))
        view.setCameraOrientation(rot)
        view.fitAll()

    def _on_normal_preset(self, idx):
        _, vec = _NORMAL_PRESETS[idx]
        self.obj.WorkNormal = FreeCAD.Vector(*vec)
        self._align_camera_to_plane()

    def _update_point_colors(self):
        n = len(self._points)
        colors = []
        for i in range(n):
            if i == self._hovered_idx:
                colors.append(self._highlight_color)
            elif i == self._selected_idx:
                colors.append(self._selection_color)
            else:
                colors.append(self._vertex_color)
        self._pt_material.diffuseColor.setNum(n)
        if colors:
            self._pt_material.diffuseColor.setValues(0, n, colors)

    def _update_quad_colors(self):
        n = len(self._quads)
        colors, alphas = [], []
        for i in range(n):
            if i == self._hovered_quad_idx:
                colors.append(self._highlight_color)
                alphas.append(0.5)
            elif i == self._selected_quad_idx:
                colors.append(self._selection_color)
                alphas.append(0.5)
            else:
                colors.append(self._edge_color)
                alphas.append(0.85)
        self._face_material.diffuseColor.setNum(n)
        self._face_material.transparency.setNum(n)
        if colors:
            self._face_material.diffuseColor.setValues(0, n, colors)
            self._face_material.transparency.setValues(0, n, alphas)

    def _rebuild_coin3d(self):
        # Points
        pts = [p["pos"] for p in self._points]
        if pts:
            self._pt_coords.point.setValues(0, len(pts), pts)
        self._pt_coords.point.setNum(len(pts))
        self._update_point_colors()

        # In-progress corners
        prog = [self._points[i]["pos"] for i in self._quad_in_progress]
        if prog:
            self._prog_coords.point.setValues(0, len(prog), prog)
        self._prog_coords.point.setNum(len(prog))

        # Quad faces + edges
        if pts and self._quads:
            self._face_coords.point.setValues(0, len(pts), pts)
            self._face_coords.point.setNum(len(pts))
            face_indices = []
            for quad in self._quads:
                q = list(quad)
                face_indices += [q[0], q[1], q[2], q[3], -1]
            self._face_set.coordIndex.setValues(0, len(face_indices), face_indices)
            self._face_set.coordIndex.setNum(len(face_indices))

            self._edge_coords.point.setValues(0, len(pts), pts)
            self._edge_coords.point.setNum(len(pts))
            edge_indices = []
            for quad in self._quads:
                q = list(quad)
                edge_indices += [q[0], q[1], q[2], q[3], q[0], -1]
            self._edge_lines.coordIndex.setValues(0, len(edge_indices), edge_indices)
            self._edge_lines.coordIndex.setNum(len(edge_indices))
        else:
            self._face_coords.point.setNum(0)
            self._face_set.coordIndex.setNum(0)
            self._edge_coords.point.setNum(0)
            self._edge_lines.coordIndex.setNum(0)
        self._update_quad_colors()

    # ------------------------------------------------------------------ Tables

    def _rebuild_tables(self):
        self._pts_table.blockSignals(True)
        self._quads_table.blockSignals(True)

        self._pts_table.setRowCount(len(self._points))
        for i, pt in enumerate(self._points):
            x, y, z = pt["pos"]
            items = [str(i), f"{x:.4f}", f"{y:.4f}", f"{z:.4f}", pt.get("clamp", "Free")]
            for col, text in enumerate(items):
                item = QtGui.QTableWidgetItem(text)
                if col == 0:
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self._pts_table.setItem(i, col, item)

        self._quads_table.setRowCount(len(self._quads))
        for i, quad in enumerate(self._quads):
            items = [str(i)] + [str(idx) for idx in quad]
            for col, text in enumerate(items):
                item = QtGui.QTableWidgetItem(text)
                if col == 0:
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self._quads_table.setItem(i, col, item)
            for axis in range(2):
                item = QtGui.QTableWidgetItem()
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(
                    QtCore.Qt.Checked if i in self._chops[axis] else QtCore.Qt.Unchecked
                )
                self._quads_table.setItem(i, 5 + axis, item)

        if 0 <= self._selected_idx < len(self._points):
            self._pts_table.selectRow(self._selected_idx)
        if 0 <= self._selected_quad_idx < len(self._quads):
            self._quads_table.selectRow(self._selected_quad_idx)

        self._pts_table.blockSignals(False)
        self._quads_table.blockSignals(False)

    def _on_point_selection_changed(self):
        self._selected_idx = self._pts_table.currentRow()
        self._update_point_colors()

    def _on_quad_selection_changed(self):
        self._selected_quad_idx = self._quads_table.currentRow()
        self._update_quad_colors()

    def _on_point_cell_changed(self, row, col):
        if col not in (1, 2, 3, 4) or row >= len(self._points):
            return
        item = self._pts_table.item(row, col)
        if item is None:
            return
        if col in (1, 2, 3):
            try:
                self._points[row]["pos"][col - 1] = float(item.text())
                self._rebuild_coin3d()
            except ValueError:
                pass
        elif col == 4:
            clamp = item.text().strip()
            if clamp in CLAMP_TYPES:
                self._points[row]["clamp"] = clamp

    def _on_quad_cell_changed(self, row, col):
        if row >= len(self._quads):
            return
        item = self._quads_table.item(row, col)
        if item is None:
            return
        if col in (1, 2, 3, 4):
            try:
                idx = int(item.text())
            except ValueError:
                return
            if 0 <= idx < len(self._points):
                self._quads[row][col - 1] = idx
                self._rebuild_coin3d()
        elif col in (5, 6):
            axis = col - 5
            if item.checkState() == QtCore.Qt.Checked:
                self._chops[axis].add(row)
            else:
                self._chops[axis].discard(row)

    # ------------------------------------------------------------------ Viewport interaction

    def _screen_to_workplane(self, sc, view):
        """Convert screen position sc=(x,y) to 3D point on the sketch work plane."""
        pt = view.getPoint(sc[0], sc[1])
        if view.getCameraType() == "Perspective":
            cam_pos = view.getCameraNode().getField("position").getValue()
            ray = [pt.x - cam_pos[0], pt.y - cam_pos[1], pt.z - cam_pos[2]]
        else:
            dv = view.getViewDirection()
            ray = [dv.x, dv.y, dv.z]
        origin = self.obj.WorkOrigin
        normal = self.obj.WorkNormal
        return _ray_plane_intersect(
            [pt.x, pt.y, pt.z],
            ray,
            [origin.x, origin.y, origin.z],
            [normal.x, normal.y, normal.z],
        )

    def _world_snap_tol(self, sc, view):
        """World-space distance corresponding to SNAP_PIXELS at screen position sc."""
        p1 = view.getPoint(sc[0], sc[1])
        p2 = view.getPoint(sc[0] + SNAP_PIXELS, sc[1])
        return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2 + (p1.z - p2.z) ** 2) ** 0.5

    def _nearest_point(self, sc, view):
        """Return index of point nearest to screen pos sc within SNAP_PIXELS, or None."""
        if not self._points:
            return None
        tol = self._world_snap_tol(sc, view)
        cursor = np.array(self._screen_to_workplane(sc, view))
        best_i, best_d = -1, float("inf")
        for i, pt in enumerate(self._points):
            d = float(np.linalg.norm(np.array(pt["pos"]) - cursor))
            if d < best_d:
                best_d = d
                best_i = i
        return best_i if best_d < tol else None

    def _quad_at_cursor(self, sc, view):
        """Return index of the first quad whose interior contains the screen pos sc, or None."""
        if not self._quads or not self._points:
            return None
        cursor = np.array(self._screen_to_workplane(sc, view))
        n = self.obj.WorkNormal
        normal = [n.x, n.y, n.z]
        for qi, quad in enumerate(self._quads):
            pts = [np.array(self._points[i]["pos"]) for i in quad]
            if _point_in_quad(cursor, pts, normal):
                return qi
        return None

    def _select_point(self, idx):
        self._selected_idx = idx
        self._pts_table.blockSignals(True)
        if idx >= 0:
            self._pts_table.selectRow(idx)
        else:
            self._pts_table.clearSelection()
        self._pts_table.blockSignals(False)
        self._update_point_colors()

    def _select_quad(self, idx):
        self._selected_quad_idx = idx
        self._quads_table.blockSignals(True)
        if idx >= 0:
            self._quads_table.selectRow(idx)
        else:
            self._quads_table.clearSelection()
        self._quads_table.blockSignals(False)
        self._update_quad_colors()

    def _on_mouse_click(self, event_cb):
        event = event_cb.getEvent()
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return

        view = FreeCADGui.ActiveDocument.ActiveView
        sc = event.getPosition()

        if event.getState() == coin.SoMouseButtonEvent.UP:
            if self._dragging:
                self._dragging = False
                self._drag_idx = -1
                self._rebuild_tables()
            return

        # DOWN from here
        if self._mode == "add_point":
            pos = self._screen_to_workplane(sc, view)
            self._points.append(_make_point(pos))
            self._rebuild_tables()
            self._rebuild_coin3d()

        elif self._mode == "add_quad":
            idx = self._nearest_point(sc, view)
            if idx is None:
                n = len(self._quad_in_progress)
                self._status.setText(f"Quad: {n}/4 — click on an existing point")
                return
            if idx not in self._quad_in_progress:
                self._quad_in_progress.append(idx)

            n = len(self._quad_in_progress)
            if n == 4:
                self._quads.append(list(self._quad_in_progress))
                self._set_mode("add_quad")  # resets _quad_in_progress, stays in mode
            else:
                self._status.setText(f"Quad: {n}/4 corners selected")

            self._rebuild_tables()
            self._rebuild_coin3d()

        elif self._mode is None:
            pt_idx = self._nearest_point(sc, view)
            if pt_idx is not None:
                self._select_point(pt_idx)
                self._select_quad(-1)
                self._dragging = True
                self._drag_idx = pt_idx
            else:
                q_idx = self._quad_at_cursor(sc, view)
                self._select_point(-1)
                self._select_quad(q_idx if q_idx is not None else -1)

    def _on_mouse_move(self, event_cb):
        sc = event_cb.getEvent().getPosition()
        view = FreeCADGui.ActiveDocument.ActiveView

        if self._dragging:
            self._points[self._drag_idx]["pos"] = self._screen_to_workplane(sc, view)
            self._rebuild_coin3d()
            return

        pt_snap = self._nearest_point(sc, view) if self._mode in ("add_point", "add_quad", None) else None
        new_pt_hover = pt_snap if pt_snap is not None else -1

        new_q_hover = -1
        if self._mode is None and pt_snap is None:
            q = self._quad_at_cursor(sc, view)
            new_q_hover = q if q is not None else -1

        if new_pt_hover == self._hovered_idx and new_q_hover == self._hovered_quad_idx:
            return
        self._hovered_idx = new_pt_hover
        self._hovered_quad_idx = new_q_hover
        self._update_point_colors()
        self._update_quad_colors()

    # ------------------------------------------------------------------ Mode management

    _MODE_STATUS = {
        "add_point":    "Click in viewport to place points — click [+] again to finish",
        "delete_point": "Click a point row to delete it — click [−] again to finish",
        "add_quad":     "Click 4 points to define a quad — click [+] again to finish",
        "delete_quad":  "Click a quad row to delete it — click [−] again to finish",
    }

    def _set_mode(self, mode):
        self._mode = mode
        self._quad_in_progress = []
        self._add_pt_btn.setChecked(mode == "add_point")
        self._del_pt_btn.setChecked(mode == "delete_point")
        self._add_quad_btn.setChecked(mode == "add_quad")
        self._del_quad_btn.setChecked(mode == "delete_quad")
        self._status.setText(self._MODE_STATUS.get(mode, ""))
        self._hovered_idx = -1
        self._hovered_quad_idx = -1
        self._update_point_colors()
        self._update_quad_colors()

    # ------------------------------------------------------------------ Button handlers

    def _toggle_add_point(self):
        self._set_mode(None if self._mode == "add_point" else "add_point")

    def _toggle_delete_point(self):
        self._set_mode(None if self._mode == "delete_point" else "delete_point")

    def _toggle_add_quad(self):
        self._set_mode(None if self._mode == "add_quad" else "add_quad")

    def _toggle_delete_quad(self):
        self._set_mode(None if self._mode == "delete_quad" else "delete_quad")

    def _delete_point(self):
        row = self._pts_table.currentRow()
        if row < 0:
            return
        if any(row in q for q in self._quads):
            self._status.setText(f"Point {row} is used by a quad — delete the quad first")
            return
        if self._selected_idx == row:
            self._selected_idx = -1
        elif self._selected_idx > row:
            self._selected_idx -= 1
        self._points.pop(row)
        self._quads = [[i if i < row else i - 1 for i in q] for q in self._quads]
        self._rebuild_tables()
        self._rebuild_coin3d()

    def _delete_quad(self):
        row = self._quads_table.currentRow()
        if row < 0:
            return
        if self._selected_quad_idx == row:
            self._selected_quad_idx = -1
        elif self._selected_quad_idx > row:
            self._selected_quad_idx -= 1
        self._quads.pop(row)
        for axis in range(2):
            self._chops[axis].discard(row)
            self._chops[axis] = {i - 1 if i > row else i for i in self._chops[axis]}
        self._rebuild_tables()
        self._rebuild_coin3d()

    def _on_pt_table_item_clicked(self, _item):
        if self._mode == "delete_point":
            self._delete_point()

    def _on_quad_table_item_clicked(self, _item):
        if self._mode == "delete_quad":
            self._delete_quad()

    # ------------------------------------------------------------------ Lifecycle

    def _cleanup(self):
        if getattr(self, "_cleaned_up", False):
            return
        self._cleaned_up = True
        view = FreeCADGui.ActiveDocument.ActiveView
        if view is None:
            return
        view.removeEventCallbackPivy(coin.SoMouseButtonEvent.getClassTypeId(), self._event_cb)
        view.removeEventCallbackPivy(coin.SoLocation2Event.getClassTypeId(), self._move_cb)
        view.getSceneGraph().removeChild(self._root)

    def _check_warnings(self):
        used = {i for q in self._quads for i in q}
        orphans = [i for i in range(len(self._points)) if i not in used]
        warnings = []
        if orphans:
            warnings.append(f"Orphan points (not in any quad): {orphans}")
        if self._quad_in_progress:
            warnings.append(f"Incomplete quad ({len(self._quad_in_progress)}/4 corners) will be discarded")
        return warnings

    def accept(self):
        warnings = self._check_warnings()
        if warnings:
            reply = QtGui.QMessageBox.question(
                self.form, "Sketch issues",
                "\n".join(warnings) + "\n\nClose anyway?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
            )
            if reply != QtGui.QMessageBox.Yes:
                return False

        self.obj.SketchPoints = list(self._points)
        self.obj.SketchQuads = list(self._quads)
        self.obj.SketchChops = [sorted(self._chops[0]), sorted(self._chops[1])]
        self._cleanup()
        self.obj.Document.recompute()
        return True

    def reject(self):
        self._cleanup()
        return True
