"""Tier 2 'Extrude' Document Object: a thin wrapper around classy_blocks' Extrude."""

import classy_blocks as cb
import FreeCAD

from .recording import (
    RecordingOperationMixin,
    add_chop_patch_properties,
    apply_chop_patch,
    loft_preview_shape,
)


class RecordingExtrude(RecordingOperationMixin, cb.Extrude):
    """A cb.Extrude that remembers its base Face's varname and amount for codegen."""

    def __init__(self, base, amount, base_varname):
        self.amount = amount
        self.base_varname = base_varname
        super().__init__(base, amount)
        self.referenced_faces = {base_varname: base}

    def to_lines(self, varname: str) -> list[str]:
        lines = [f"{varname} = cb.Extrude({self.base_varname}, {list(self.amount)})"]
        lines.extend(self.chop_patch_lines(varname))
        return lines


class ExtrudeProxy:
    """Proxy for a Part::FeaturePython object representing a classy_blocks Extrude."""

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLink", "Base", "ClassyFoundry", "Face to extrude from"
        )
        obj.addProperty(
            "App::PropertyVector", "Amount", "ClassyFoundry", "Extrusion vector"
        ).Amount = FreeCAD.Vector(0, 0, 1)
        add_chop_patch_properties(obj)

    def execute(self, obj):
        base_obj = obj.Base
        if base_obj is None:
            return
        if not hasattr(base_obj.Proxy, "face"):
            base_obj.recompute(True)
        if not hasattr(base_obj.Proxy, "face"):
            return

        amount = [obj.Amount.x, obj.Amount.y, obj.Amount.z]
        extrude = RecordingExtrude(base_obj.Proxy.face, amount, base_obj.Name.lower())
        apply_chop_patch(obj, extrude)
        self.operation = extrude
        obj.Shape = loft_preview_shape(extrude)

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class ExtrudeViewProvider:
    """Minimal ViewProvider so the Extrude's Shape renders in the 3D view."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ""

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


def make_extrude(doc, name="Extrude"):
    """Create a new Extrude Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    ExtrudeProxy(obj)
    if FreeCAD.GuiUp:
        ExtrudeViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
