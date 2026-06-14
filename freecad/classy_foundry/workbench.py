import FreeCADGui

from .resources import Resources


class ClassyFoundryWorkbench(FreeCADGui.Workbench):
    MenuText = "classy_foundry"
    ToolTip = "GUI for classy_blocks: build OpenFOAM blockMesh meshes visually"
    Icon = Resources.icon("classy_foundry-wb.svg")

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    def Initialize(self):
        from .commands import (
            CreateBoxCommand,
            CreateExtrudeCommand,
            CreateFaceCommand,
            CreateLoftCommand,
            CreateMeshCommand,
            ExportScriptCommand,
        )

        FreeCADGui.addCommand("ClassyFoundry_CreateBox", CreateBoxCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateExtrude", CreateExtrudeCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateFace", CreateFaceCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateLoft", CreateLoftCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateMesh", CreateMeshCommand())
        FreeCADGui.addCommand("ClassyFoundry_ExportScript", ExportScriptCommand())

        commands = [
            "ClassyFoundry_CreateBox",
            "ClassyFoundry_CreateExtrude",
            "ClassyFoundry_CreateFace",
            "ClassyFoundry_CreateLoft",
            "ClassyFoundry_CreateMesh",
            "ClassyFoundry_ExportScript",
        ]
        self.appendToolbar("classy_foundry", commands)
        self.appendMenu("classy_foundry", commands)
