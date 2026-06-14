"""Root 'Mesh' Document Object: collects elements and generates a classy_blocks script."""

import os
import tempfile

import classy_blocks as cb
import FreeCAD


class MeshProxy:
    """Proxy for an App::FeaturePython object representing a classy_blocks Mesh."""

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLinkList",
            "Elements",
            "ClassyFoundry",
            "Elements included in this mesh",
        )
        obj.addProperty(
            "App::PropertyString",
            "WritePath",
            "ClassyFoundry",
            "Path passed to mesh.write() in the generated script",
        ).WritePath = "case/system/blockMeshDict"

    def execute(self, obj):
        pass

    def _elements_with_operation(self, obj):
        """Return (element, RecordingOperation-like instance) pairs, recomputing as needed."""
        pairs = []
        for element in obj.Elements:
            if not hasattr(element.Proxy, "operation"):
                element.recompute(True)
            if hasattr(element.Proxy, "operation"):
                pairs.append((element, element.Proxy.operation))
        return pairs

    def build_cb_mesh(self, obj) -> cb.Mesh:
        """Build a live classy_blocks Mesh from this object's Elements."""
        mesh = cb.Mesh()
        for _, operation in self._elements_with_operation(obj):
            mesh.add(operation)
        return mesh

    def validate(self, obj) -> str | None:
        """Try to assemble and grade the mesh. Return an error message, or None if OK."""
        mesh = self.build_cb_mesh(obj)
        try:
            mesh.assemble()
            with tempfile.TemporaryDirectory() as tmpdir:
                mesh.write(os.path.join(tmpdir, "blockMeshDict"))
        except Exception as err:
            return str(err)
        return None

    def to_script_lines(self, obj) -> list[str]:
        lines = ["import classy_blocks as cb", "", "mesh = cb.Mesh()", ""]
        emitted_faces = set()
        for element, operation in self._elements_with_operation(obj):
            for varname, face in operation.referenced_faces.items():
                if varname not in emitted_faces:
                    lines.extend(face.to_lines(varname))
                    lines.append("")
                    emitted_faces.add(varname)

            varname = element.Name.lower()
            lines.extend(operation.to_lines(varname))
            lines.append(f"mesh.add({varname})")
            lines.append("")
        lines.append(f"mesh.write({obj.WritePath!r})")
        return lines

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class MeshViewProvider:
    """ViewProvider that nests the Mesh's Elements under it in the tree view."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def claimChildren(self):
        return self.Object.Elements

    def doubleClicked(self, vobj):
        import FreeCADGui

        from ..taskpanels.mesh_panel import MeshTaskPanel

        FreeCADGui.Control.showDialog(MeshTaskPanel(vobj.Object))
        return True

    def getIcon(self):
        return ""

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


def make_mesh(doc, name="Mesh"):
    """Create a new Mesh Document Object in `doc`."""
    obj = doc.addObject("App::FeaturePython", name)
    MeshProxy(obj)
    if FreeCAD.GuiUp:
        MeshViewProvider(obj.ViewObject)
    doc.recompute()
    return obj


def add_element(mesh_obj, element):
    """Add `element` to mesh_obj's Elements list."""
    elements = mesh_obj.Elements
    elements.append(element)
    mesh_obj.Elements = elements
