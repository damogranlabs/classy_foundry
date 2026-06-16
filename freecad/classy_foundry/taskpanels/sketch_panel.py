"""Task panel for editing a MappedSketch: point placement + quad definition."""

import numpy as np
from pivy import coin
from PySide import QtCore, QtGui

import FreeCAD
import FreeCADGui

CLAMP_TYPES = ["Free", "Fixed", "OnCurve", "OnSurface"]
SNAP_TOLERANCE = 0.5


def _make_point(pos):
    return {"pos": list(pos), "clamp": "Free", "curve_idx": None, "relational": None}


def _project_to_plane(pt, origin, normal):
    n = np.array(normal)
    norm = np.linalg.norm(n)
    if norm < 1e-10:
        n = np.array([0.0, 0.0, 1.0])
    else:
        n = n / norm
    p = np.array(pt)
    o = np.array(origin)
    return (p - np.dot(p - o, n) * n).tolist()


class SketchTaskPanel:
    def __init__(self, obj):
        self.obj = obj
        self._points = [dict(p) for p in obj.SketchPoints]
        self._quads = [list(q) for q in obj.SketchQuads]
        self._mode = None
        self._quad_in_progress = []

        self._build_ui()
        self._setup_coin3d()

        view = FreeCADGui.ActiveDocument.ActiveView
        self._event_cb = view.addEventCallbackPivy(
            coin.SoMouseButtonEvent.getClassTypeId(), self._on_mouse_click
        )

        self._rebuild_tables()
        self._rebuild_coin3d()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self.form = QtGui.QWidget()
        self.form.setWindowTitle("Sketch Editor")
        layout = QtGui.QVBoxLayout(self.form)

        # Points section
        layout.addWidget(QtGui.QLabel("<b>Points</b>"))
        pts_btns = QtGui.QHBoxLayout()
        self._add_pt_btn = QtGui.QPushButton("+")
        self._add_pt_btn.setToolTip("Click in viewport to place a new point")
        self._del_pt_btn = QtGui.QPushButton("−")
        self._del_pt_btn.setToolTip("Delete selected point (blocked if in use)")
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
        self._add_quad_btn.setToolTip("Click 4 points in viewport to define a quad")
        self._del_quad_btn = QtGui.QPushButton("−")
        self._del_quad_btn.setToolTip("Delete selected quad")
        quad_btns.addWidget(self._add_quad_btn)
        quad_btns.addWidget(self._del_quad_btn)
        quad_btns.addStretch()
        layout.addLayout(quad_btns)

        self._quads_table = QtGui.QTableWidget(0, 5)
        self._quads_table.setHorizontalHeaderLabels(["#", "P0", "P1", "P2", "P3"])
        self._quads_table.horizontalHeader().setStretchLastSection(True)
        self._quads_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        layout.addWidget(self._quads_table)

        self._status = QtGui.QLabel("")
        layout.addWidget(self._status)

        self._add_pt_btn.clicked.connect(self._start_add_point)
        self._del_pt_btn.clicked.connect(self._delete_point)
        self._add_quad_btn.clicked.connect(self._start_add_quad)
        self._del_quad_btn.clicked.connect(self._delete_quad)
        self._pts_table.cellChanged.connect(self._on_point_cell_changed)
        self._quads_table.cellChanged.connect(self._on_quad_cell_changed)

    # ------------------------------------------------------------------ Coin3D

    def _setup_coin3d(self):
        self._root = coin.SoSeparator()

        # All point markers — white
        pt_sep = coin.SoSeparator()
        pt_col = coin.SoBaseColor()
        pt_col.rgb = (1, 1, 1)
        self._pt_coords = coin.SoCoordinate3()
        pt_markers = coin.SoMarkerSet()
        pt_markers.markerIndex.setValue(coin.SoMarkerSet.CIRCLE_FILLED_9_9)
        pt_sep.addChild(pt_col)
        pt_sep.addChild(self._pt_coords)
        pt_sep.addChild(pt_markers)
        self._root.addChild(pt_sep)

        # In-progress quad corner markers — yellow
        prog_sep = coin.SoSeparator()
        prog_col = coin.SoBaseColor()
        prog_col.rgb = (1, 1, 0)
        self._prog_coords = coin.SoCoordinate3()
        prog_markers = coin.SoMarkerSet()
        prog_markers.markerIndex.setValue(coin.SoMarkerSet.CIRCLE_FILLED_9_9)
        prog_sep.addChild(prog_col)
        prog_sep.addChild(self._prog_coords)
        prog_sep.addChild(prog_markers)
        self._root.addChild(prog_sep)

        # Quad edge lines — light grey
        edge_sep = coin.SoSeparator()
        edge_col = coin.SoBaseColor()
        edge_col.rgb = (0.6, 0.6, 0.6)
        self._edge_coords = coin.SoCoordinate3()
        self._edge_lines = coin.SoIndexedLineSet()
        edge_sep.addChild(edge_col)
        edge_sep.addChild(self._edge_coords)
        edge_sep.addChild(self._edge_lines)
        self._root.addChild(edge_sep)

        FreeCADGui.ActiveDocument.ActiveView.getSceneGraph().addChild(self._root)

    def _rebuild_coin3d(self):
        # Points
        pts = [p["pos"] for p in self._points]
        if pts:
            self._pt_coords.point.setValues(0, len(pts), pts)
        self._pt_coords.point.setNum(len(pts))

        # In-progress corners
        prog = [self._points[i]["pos"] for i in self._quad_in_progress]
        if prog:
            self._prog_coords.point.setValues(0, len(prog), prog)
        self._prog_coords.point.setNum(len(prog))

        # Quad edges
        if pts and self._quads:
            self._edge_coords.point.setValues(0, len(pts), pts)
            self._edge_coords.point.setNum(len(pts))
            indices = []
            for quad in self._quads:
                q = list(quad)
                indices += [q[0], q[1], q[2], q[3], q[0], -1]
            self._edge_lines.coordIndex.setValues(0, len(indices), indices)
            self._edge_lines.coordIndex.setNum(len(indices))
        else:
            self._edge_coords.point.setNum(0)
            self._edge_lines.coordIndex.setNum(0)

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

        self._pts_table.blockSignals(False)
        self._quads_table.blockSignals(False)

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
        if col not in (1, 2, 3, 4) or row >= len(self._quads):
            return
        item = self._quads_table.item(row, col)
        if item is None:
            return
        try:
            idx = int(item.text())
        except ValueError:
            return
        if 0 <= idx < len(self._points):
            self._quads[row][col - 1] = idx
            self._rebuild_coin3d()

    # ------------------------------------------------------------------ Viewport interaction

    def _click_3d_pos(self, event):
        """Get click position projected onto the sketch work plane."""
        sc_pos = event.getPosition()
        view = FreeCADGui.ActiveDocument.ActiveView
        pt = view.getPoint(sc_pos[0], sc_pos[1])
        origin = self.obj.WorkOrigin
        normal = self.obj.WorkNormal
        return _project_to_plane(
            [pt.x, pt.y, pt.z],
            [origin.x, origin.y, origin.z],
            [normal.x, normal.y, normal.z],
        )

    def _nearest_point(self, pos):
        """Return index of nearest existing point within SNAP_TOLERANCE, or None."""
        if not self._points:
            return None
        p = np.array(pos)
        dists = [np.linalg.norm(np.array(pt["pos"]) - p) for pt in self._points]
        i = int(np.argmin(dists))
        return i if dists[i] < SNAP_TOLERANCE else None

    def _snap_or_create(self, pos):
        """Return point index, creating a new point if none is close enough."""
        snap = self._nearest_point(pos)
        if snap is not None:
            return snap
        self._points.append(_make_point(pos))
        return len(self._points) - 1

    def _on_mouse_click(self, event_cb):
        event = event_cb.getEvent()
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return
        if event.getState() != coin.SoMouseButtonEvent.DOWN:
            return

        pos = self._click_3d_pos(event)

        if self._mode == "add_point":
            self._points.append(_make_point(pos))
            self._mode = None
            self._status.setText("")
            self._rebuild_tables()
            self._rebuild_coin3d()

        elif self._mode == "add_quad":
            idx = self._snap_or_create(pos)
            if idx not in self._quad_in_progress:
                self._quad_in_progress.append(idx)

            n = len(self._quad_in_progress)
            self._status.setText(f"Quad: {n}/4 corners — click {'more points' if n < 4 else 'done'}")

            if n == 4:
                self._quads.append(list(self._quad_in_progress))
                self._quad_in_progress = []
                self._mode = None
                self._status.setText("")

            self._rebuild_tables()
            self._rebuild_coin3d()

    # ------------------------------------------------------------------ Button handlers

    def _start_add_point(self):
        self._mode = "add_point"
        self._quad_in_progress = []
        self._status.setText("Click in viewport to place a point")

    def _start_add_quad(self):
        self._mode = "add_quad"
        self._quad_in_progress = []
        self._status.setText("Click 4 points (snap to existing or create new)")

    def _delete_point(self):
        row = self._pts_table.currentRow()
        if row < 0:
            return
        if any(row in q for q in self._quads):
            self._status.setText(f"Point {row} is used by a quad — delete the quad first")
            return
        self._points.pop(row)
        self._quads = [[i if i < row else i - 1 for i in q] for q in self._quads]
        self._rebuild_tables()
        self._rebuild_coin3d()

    def _delete_quad(self):
        row = self._quads_table.currentRow()
        if row >= 0:
            self._quads.pop(row)
            self._rebuild_tables()
            self._rebuild_coin3d()

    # ------------------------------------------------------------------ Lifecycle

    def _cleanup(self):
        view = FreeCADGui.ActiveDocument.ActiveView
        view.removeEventCallbackPivy(coin.SoMouseButtonEvent.getClassTypeId(), self._event_cb)
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
        self.obj.Document.recompute()
        self._cleanup()
        return True

    def reject(self):
        self._cleanup()
        return True
