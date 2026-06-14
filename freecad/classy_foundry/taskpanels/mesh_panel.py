"""Task panel for editing Mesh settings (write path, and later scale, default patch, ...)."""

from PySide import QtGui


class MeshTaskPanel:
    def __init__(self, obj):
        self.obj = obj

        self.form = QtGui.QWidget()
        self.form.setWindowTitle("Mesh settings")
        layout = QtGui.QFormLayout(self.form)

        self.write_path_edit = QtGui.QLineEdit(obj.WritePath)
        layout.addRow("Write path", self.write_path_edit)

    def accept(self):
        self.obj.WritePath = self.write_path_edit.text()
        self.obj.Document.recompute()
        return True

    def reject(self):
        return True
