"""Root 'Mesh' Document Object: collects elements and generates a classy_blocks script."""

import os
import tempfile

import classy_blocks as cb
import FreeCAD

from .recording import ProxyBase, ViewProviderBase


def _mesh_add_name(element):
    """Walk up any transform chain to find the root source varname for mesh.add()."""
    while hasattr(element, "TransformType") and element.Source is not None:
        element = element.Source
    return element.Name.lower()


class MeshProxy(ProxyBase):
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

    def _resolve_solid(self, element):
        """Return the cb solid (operation or shape) from an element, recomputing if needed."""
        for attr in ("operation", "shape"):
            val = getattr(element.Proxy, attr, None)
            if val is not None:
                return val
        element.recompute(True)
        for attr in ("operation", "shape"):
            val = getattr(element.Proxy, attr, None)
            if val is not None:
                return val
        return None

    def build_cb_mesh(self, obj) -> cb.Mesh:
        """Build a live classy_blocks Mesh from this object's Elements."""
        mesh = cb.Mesh()
        for element in obj.Elements:
            solid = self._resolve_solid(element)
            if solid is not None:
                mesh.add(solid)
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
        emitted = set()
        for element in obj.Elements:
            self._emit_element(element, lines, emitted)
            add_name = _mesh_add_name(element)
            lines.append(f"mesh.add({add_name})")
            lines.append("")
        lines.append(f"mesh.write({obj.WritePath!r})")
        return lines

    def _emit_element(self, element, lines, emitted):
        """Emit codegen lines for an element (and its dependencies) if not already emitted."""
        name = element.Name.lower()
        if name in emitted:
            return
        emitted.add(name)
        proxy = element.Proxy

        if hasattr(element, "TransformType"):
            if element.Source is not None:
                self._emit_element(element.Source, lines, emitted)
            lines.extend(proxy.to_lines(element))
            lines.append("")

        elif hasattr(element, "CopyOf"):
            if element.CopyOf is not None:
                self._emit_element(element.CopyOf, lines, emitted)
            lines.extend(proxy.to_lines(element, name))
            lines.append("")

        elif hasattr(proxy, "shape") and hasattr(element, "Sketch"):
            self._emit_sketch_lines(element, lines, emitted)
            lines.extend(proxy.to_lines(element, name))
            lines.append("")

        elif hasattr(proxy, "operation"):
            operation = proxy.operation
            for dep_name, face in operation.referenced_faces.items():
                if dep_name not in emitted:
                    lines.extend(face.to_lines(dep_name))
                    lines.append("")
                    emitted.add(dep_name)
            lines.extend(operation.to_lines(name))
            lines.append("")

    @staticmethod
    def _emit_sketch_lines(element, lines, emitted):
        sketch_obj = element.Sketch
        if sketch_obj is None:
            return
        sketch_varname = sketch_obj.Name.lower()
        if sketch_varname not in emitted:
            lines.extend(sketch_obj.Proxy.to_lines(sketch_obj, sketch_varname))
            lines.append("")
            emitted.add(sketch_varname)


class MeshViewProvider(ViewProviderBase):
    """ViewProvider that nests the Mesh's Elements under it in the tree view."""

    def claimChildren(self):
        return self.Object.Elements

    def doubleClicked(self, vobj):
        import FreeCADGui

        from ..taskpanels.mesh_panel import MeshTaskPanel

        FreeCADGui.Control.showDialog(MeshTaskPanel(vobj.Object))
        return True


def find_mesh(doc):
    """Return the document's Mesh object, or None if it doesn't have one yet."""
    return next((o for o in doc.Objects if isinstance(getattr(o, "Proxy", None), MeshProxy)), None)


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
