import os

import FreeCAD
import FreeCADGui

from .objects.box import make_box
from .objects.extracted_face import make_extracted_face
from .objects.extrude import make_extrude
from .objects.face import make_face
from .objects.loft import make_loft
from .objects.mesh import add_element, find_mesh, make_mesh
from .objects.recording import FaceProxyBase, OperationProxyBase, resolve_operation
from .objects.revolve import make_revolve
from .script_panel import show_script_panel


def _selected_faces(doc, count, error):
    """Return `count` selected Face objects in selection order, or None (with an error) if not."""
    faces = [o for o in FreeCADGui.Selection.getSelection(doc.Name) if isinstance(o.Proxy, FaceProxyBase)]
    if len(faces) != count:
        FreeCAD.Console.PrintError(error)
        return None
    return faces


def _selected_operation_point(doc, error):
    """Return (obj, operation, picked point) for a single picked face of an Operation, or None."""
    selection = FreeCADGui.Selection.getSelectionEx(doc.Name)
    if len(selection) != 1 or not selection[0].PickedPoints:
        FreeCAD.Console.PrintError(error)
        return None

    obj = selection[0].Object
    if not isinstance(obj.Proxy, OperationProxyBase):
        FreeCAD.Console.PrintError(error)
        return None

    operation = resolve_operation(obj)
    if operation is None:
        FreeCAD.Console.PrintError(error)
        return None

    return obj, operation, selection[0].PickedPoints[0]


class CreateBoxCommand:
    def GetResources(self):
        return {
            "MenuText": "Box",
            "ToolTip": "Create a classy_blocks Box operation",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        mesh_obj = find_mesh(doc)
        box_obj = make_box(doc)
        add_element(mesh_obj, box_obj)

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and find_mesh(doc) is not None


class CreateExtrudeCommand:
    def GetResources(self):
        return {
            "MenuText": "Extrude",
            "ToolTip": "Create a classy_blocks Extrude operation from a Face",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        faces = _selected_faces(doc, 1, "Select exactly one Face to extrude\n")
        if faces is None:
            return

        mesh_obj = find_mesh(doc)
        extrude_obj = make_extrude(doc)
        extrude_obj.Base = faces[0]
        add_element(mesh_obj, extrude_obj)
        doc.recompute()

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and find_mesh(doc) is not None


class CreateLoftCommand:
    def GetResources(self):
        return {
            "MenuText": "Loft",
            "ToolTip": "Create a classy_blocks Loft operation between two Faces",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        faces = _selected_faces(doc, 2, "Select exactly two Faces (bottom, then top) to loft\n")
        if faces is None:
            return

        mesh_obj = find_mesh(doc)
        loft_obj = make_loft(doc)
        loft_obj.BottomFace, loft_obj.TopFace = faces
        add_element(mesh_obj, loft_obj)
        doc.recompute()

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and find_mesh(doc) is not None


class CreateRevolveCommand:
    def GetResources(self):
        return {
            "MenuText": "Revolve",
            "ToolTip": "Create a classy_blocks Revolve operation from a Face",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        faces = _selected_faces(doc, 1, "Select exactly one Face to revolve\n")
        if faces is None:
            return

        mesh_obj = find_mesh(doc)
        revolve_obj = make_revolve(doc)
        revolve_obj.Base = faces[0]
        add_element(mesh_obj, revolve_obj)
        doc.recompute()

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and find_mesh(doc) is not None


class ExtractFaceCommand:
    def GetResources(self):
        return {
            "MenuText": "Extract face",
            "ToolTip": "Create a Face referencing one side of an operation",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        result = _selected_operation_point(
            doc, "Pick a face of a Box/Extrude/Loft/Revolve to extract\n"
        )
        if result is None:
            return

        source_obj, operation, point = result
        side = operation.get_closest_side([point.x, point.y, point.z])
        make_extracted_face(doc, source_obj, side)

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and find_mesh(doc) is not None


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
        return doc is None or find_mesh(doc) is None


class ShowScriptCommand:
    def GetResources(self):
        return {
            "MenuText": "Script preview",
            "ToolTip": "Show/refresh the generated classy_blocks script",
        }

    def Activated(self):
        show_script_panel()

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and find_mesh(doc) is not None


class ExportScriptCommand:
    def GetResources(self):
        return {
            "MenuText": "Export script",
            "ToolTip": "Export the Mesh as a classy_blocks Python script",
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        doc.recompute()

        mesh_obj = find_mesh(doc)
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
        return doc is not None and find_mesh(doc) is not None
