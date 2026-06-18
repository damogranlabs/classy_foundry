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
            CreateChopCommand,
            CreateCopyCommand,
            CreateCurveCommand,
            CreateExtrudeCommand,
            CreateExtrudedShapeCommand,
            CreateFaceCommand,
            CreateLoftCommand,
            CreateLoftedShapeCommand,
            CreateMappedSketchCommand,
            CreateMeshCommand,
            CreateRevolveCommand,
            CreateRevolvedShapeCommand,
            CreateTransformCommand,
            ExportScriptCommand,
            ExtractFaceCommand,
            ShowScriptCommand,
        )

        FreeCADGui.addCommand("ClassyFoundry_CreateBox", CreateBoxCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateChop", CreateChopCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateCopy", CreateCopyCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateCurve", CreateCurveCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateExtrude", CreateExtrudeCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateExtrudedShape", CreateExtrudedShapeCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateLoftedShape", CreateLoftedShapeCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateRevolvedShape", CreateRevolvedShapeCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateFace", CreateFaceCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateLoft", CreateLoftCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateMappedSketch", CreateMappedSketchCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateRevolve", CreateRevolveCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateTransform", CreateTransformCommand())
        FreeCADGui.addCommand("ClassyFoundry_ExtractFace", ExtractFaceCommand())
        FreeCADGui.addCommand("ClassyFoundry_CreateMesh", CreateMeshCommand())
        FreeCADGui.addCommand("ClassyFoundry_ExportScript", ExportScriptCommand())
        FreeCADGui.addCommand("ClassyFoundry_ShowScript", ShowScriptCommand())

        commands = [
            "ClassyFoundry_CreateBox",
            "ClassyFoundry_CreateChop",
            "ClassyFoundry_CreateCopy",
            "ClassyFoundry_CreateExtrude",
            "ClassyFoundry_CreateExtrudedShape",
            "ClassyFoundry_CreateLoftedShape",
            "ClassyFoundry_CreateRevolvedShape",
            "ClassyFoundry_CreateLoft",
            "ClassyFoundry_CreateRevolve",
            "ClassyFoundry_CreateTransform",
            "ClassyFoundry_CreateFace",
            "ClassyFoundry_ExtractFace",
            "ClassyFoundry_CreateCurve",
            "ClassyFoundry_CreateMappedSketch",
            "ClassyFoundry_CreateMesh",
            "ClassyFoundry_ShowScript",
            "ClassyFoundry_ExportScript",
        ]
        self.appendToolbar("classy_foundry", commands)
        self.appendMenu("classy_foundry", commands)
