import FreeCADGui

from .resources import Resources
from .workbench import ClassyFoundryWorkbench

Resources.gui_register_icons()
Resources.gui_register_translations()

# Add workbench to the FreeCAD Gui (creates a class instance)
FreeCADGui.addWorkbench(ClassyFoundryWorkbench())
