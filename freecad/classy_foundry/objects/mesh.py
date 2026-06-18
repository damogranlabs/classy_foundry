"""Root 'Mesh' Document Object: collects elements and generates a classy_blocks script."""

import os
import tempfile

import classy_blocks as cb
import FreeCAD

from .recording import ProxyBase, ViewProviderBase


def _is_modifier(element):
    return getattr(element.Proxy, "IS_MODIFIER", False)


def _dependencies(element):
    """Return dependency objects (sketches, faces) of an element.

    For SKETCH_LINKS the full Copy/Transform chain is walked so that intermediate
    objects (the Copy and any Transform modifiers between a LoftedShape and its root
    MappedSketch) are treated as dependencies and hidden/excluded from mesh.add().
    """
    deps = []
    for name in getattr(element.Proxy, "SKETCH_LINKS", ()):
        linked = getattr(element, name, None)
        while linked is not None:
            if linked not in deps:
                deps.append(linked)
            if hasattr(linked, "CopyOf"):
                linked = linked.CopyOf
            elif hasattr(linked, "Source"):
                linked = linked.Source
            else:
                break
    for name in getattr(element.Proxy, "FACE_LINKS", ()):
        linked = getattr(element, name, None)
        if linked is not None:
            deps.append(linked)
    return deps


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
        if not FreeCAD.GuiUp:
            return
        hidden = set()
        for element in obj.Elements:
            if _is_modifier(element):
                source = getattr(element, "Source", None)
                if source is not None:
                    hidden.add(source)
            for dep in _dependencies(element):
                hidden.add(dep)
        for element in obj.Elements:
            element.ViewObject.Visibility = element not in hidden

    def _addable_elements(self, obj):
        """Return elements that get mesh.add() — not modifiers and not dependencies."""
        dep_set = set()
        for element in obj.Elements:
            for dep in _dependencies(element):
                dep_set.add(dep)
        return [e for e in obj.Elements if not _is_modifier(e) and e not in dep_set]

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

    def _final_solid(self, element, obj):
        """Walk modifier chain to get the fully-modified solid for an addable element."""
        last_modifier = {}
        for e in obj.Elements:
            if _is_modifier(e):
                source = getattr(e, "Source", None)
                if source is not None:
                    last_modifier[source] = e
        target = element
        while target in last_modifier:
            target = last_modifier[target]
        return self._resolve_solid(target)

    def build_cb_mesh(self, obj) -> cb.Mesh:
        """Build a live classy_blocks Mesh from this object's Elements."""
        mesh = cb.Mesh()
        for element in self._addable_elements(obj):
            solid = self._final_solid(element, obj)
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

        for element in self._addable_elements(obj):
            lines.append(f"mesh.add({element.Name.lower()})")
        lines.append("")
        lines.append(f"mesh.write({obj.WritePath!r})")
        return lines

    def _emit_element(self, element, lines, emitted):
        """Emit codegen lines for an element if not already emitted."""
        name = element.Name.lower()
        if name in emitted:
            return
        emitted.add(name)
        proxy = element.Proxy

        if _is_modifier(element):
            lines.extend(proxy.to_lines(element))
            lines.append("")

        elif hasattr(element, "CopyOf"):
            lines.extend(proxy.to_lines(element, name))
            lines.append("")

        elif hasattr(proxy, "shape") and getattr(proxy, "SKETCH_LINKS", None):
            for link_name in proxy.SKETCH_LINKS:
                self._emit_single_sketch(getattr(element, link_name, None), lines, emitted)
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
    def _emit_single_sketch(sketch_obj, lines, emitted):
        if sketch_obj is None:
            return
        # Walk Copy/Transform chain to find the root MappedSketch to emit
        current = sketch_obj
        while current is not None and getattr(getattr(current, "Proxy", None), "sketch", None) is None:
            current = getattr(current, "CopyOf", None) or getattr(current, "Source", None)
        if current is None:
            return
        sketch_varname = current.Name.lower()
        if sketch_varname not in emitted:
            lines.extend(current.Proxy.to_lines(current, sketch_varname))
            lines.append("")
            emitted.add(sketch_varname)


class MeshViewProvider(ViewProviderBase):
    """ViewProvider that nests all Elements (and their deps) under the Mesh."""

    def claimChildren(self):
        elements = list(self.Object.Elements)
        claimed = set(elements)
        result = []
        for element in elements:
            for dep in _dependencies(element):
                if dep not in claimed:
                    result.append(dep)
                    claimed.add(dep)
            result.append(element)
        return result

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
    elements = list(mesh_obj.Elements)
    elements.append(element)
    mesh_obj.Elements = elements


def insert_element_after(mesh_obj, element, after):
    """Insert element after `after` in mesh_obj's Elements, or append."""
    elements = list(mesh_obj.Elements)
    if after in elements:
        elements.insert(elements.index(after) + 1, element)
    else:
        elements.append(element)
    mesh_obj.Elements = elements
