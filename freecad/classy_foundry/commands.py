import os

import FreeCAD

from .objects.box import make_box
from .objects.extrude import make_extrude
from .objects.face import make_face
from .objects.loft import make_loft
from .objects.mesh import MeshProxy, add_element, make_mesh


def _find_mesh(doc):
    """Return the document's Mesh object, or None if it doesn't have one yet."""
    return next((o for o in doc.Objects if isinstance(getattr(o, "Proxy", None), MeshProxy)), None)


class CreateBoxCommand:
    def GetResources(self):
        return {
            "MenuText": "Box",
            "ToolTip": "Create a classy_blocks Box operation",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        mesh_obj = _find_mesh(doc)
        box_obj = make_box(doc)
        add_element(mesh_obj, box_obj)

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and _find_mesh(doc) is not None


class CreateExtrudeCommand:
    def GetResources(self):
        return {
            "MenuText": "Extrude",
            "ToolTip": "Create a classy_blocks Extrude operation from a Face",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        mesh_obj = _find_mesh(doc)
        extrude_obj = make_extrude(doc)
        add_element(mesh_obj, extrude_obj)

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and _find_mesh(doc) is not None


class CreateLoftCommand:
    def GetResources(self):
        return {
            "MenuText": "Loft",
            "ToolTip": "Create a classy_blocks Loft operation between two Faces",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        mesh_obj = _find_mesh(doc)
        loft_obj = make_loft(doc)
        add_element(mesh_obj, loft_obj)

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and _find_mesh(doc) is not None


class CreateFaceCommand:
    def GetResources(self):
        return {
            "MenuText": "Face",
            "ToolTip": "Create a classy_blocks Face (reusable 2D profile)",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        make_face(doc)

    def IsActive(self):
        return True


class CreateMeshCommand:
    def GetResources(self):
        return {
            "MenuText": "Mesh",
            "ToolTip": "Create the Mesh root object",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        make_mesh(doc)

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is None or _find_mesh(doc) is None


class ExportScriptCommand:
    def GetResources(self):
        return {
            "MenuText": "Export script",
            "ToolTip": "Export the Mesh as a classy_blocks Python script",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        doc.recompute()

        mesh_obj = _find_mesh(doc)
        if mesh_obj is None:
            FreeCAD.Console.PrintError("No Mesh object in document\n")
            return

        error = mesh_obj.Proxy.validate(mesh_obj)
        if error is not None:
            FreeCAD.Console.PrintError(f"Mesh is not valid, not exporting: {error}\n")
            return

        lines = mesh_obj.Proxy.to_script_lines(mesh_obj)

        doc_dir = os.path.dirname(doc.FileName) if doc.FileName else os.path.expanduser("~")
        out_path = os.path.join(doc_dir, f"{mesh_obj.Name.lower()}.py")
        with open(out_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        FreeCAD.Console.PrintMessage(f"Wrote {out_path}\n")

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and _find_mesh(doc) is not None
