"""Dockable panel showing the generated classy_blocks script for the active document's Mesh.

Generation re-runs Mesh.validate() (mesh.assemble() + a temporary mesh.write()),
which can be slow for larger meshes - so the panel only refreshes on demand,
via its "Refresh" button, rather than reacting to every recompute.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

from .objects.mesh import find_mesh


class ScriptPanel(QtGui.QDockWidget):
    """Dock widget with a 'Refresh' button and a read-only view of the generated script."""

    def __init__(self):
        super().__init__("classy_blocks script")
        self.setObjectName("ClassyFoundryScriptPanel")

        widget = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(widget)

        refresh_button = QtGui.QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        self.text_edit = QtGui.QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QtGui.QFont("Monospace"))
        layout.addWidget(self.text_edit)

        self.setWidget(widget)

    def refresh(self):
        doc = FreeCAD.ActiveDocument
        mesh_obj = find_mesh(doc) if doc is not None else None
        if mesh_obj is None:
            self.text_edit.setPlainText("# No Mesh object in the active document\n")
            return

        doc.recompute()
        error = mesh_obj.Proxy.validate(mesh_obj)
        if error is not None:
            self.text_edit.setPlainText(f"# Mesh is not valid:\n# {error}\n")
            return

        lines = mesh_obj.Proxy.to_script_lines(mesh_obj)
        self.text_edit.setPlainText("\n".join(lines))


_panel = None


def show_script_panel():
    """Show the script panel, creating and docking it on first use, and refresh it."""
    global _panel
    if _panel is None:
        _panel = ScriptPanel()
        FreeCADGui.getMainWindow().addDockWidget(QtCore.Qt.RightDockWidgetArea, _panel)

    _panel.refresh()
    _panel.show()
    _panel.raise_()
