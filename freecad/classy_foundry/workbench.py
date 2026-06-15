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
            CreateRevolveCommand,
            ExportScriptCommand,
            ExtractFaceCommand,
            ShowScriptCommand,
        )

        FreeCADGui.addCommand("ClassyFoundry_CreateBox", CreateBoxCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateExtrude", CreateExtrudeCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateFace", CreateFaceCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateLoft", CreateLoftCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateRevolve", CreateRevolveCommand())
        FreeCADGui.addCommand("ClassyFoundry_ExtractFace", ExtractFaceCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateMesh", CreateMeshCommand())
        FreeCADGui.addCommand("ClassyFoundry_ExportScript", ExportScriptCommand())
        FreeCADGui.addCommand("ClassyFoundry_ShowScript", ShowScriptCommand())

        commands = [
            "ClassyFoundry_CreateBox",
            "ClassyFoundry_CreateExtrude",
            "ClassyFoundry_CreateLoft",
            "ClassyFoundry_CreateRevolve",
            "ClassyFoundry_CreateFace",
            "ClassyFoundry_ExtractFace",
            "ClassyFoundry_CreateMesh",
            "ClassyFoundry_ShowScript",
            "ClassyFoundry_ExportScript",
        ]
        self.appendToolbar("classy_foundry", commands)
        self.appendMenu("classy_foundry", commands)
