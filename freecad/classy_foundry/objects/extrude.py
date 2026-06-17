"""Tier 2 'Extrude' Document Object: a thin wrapper around classy_blocks' Extrude."""

import classy_blocks as cb
import FreeCAD

from .recording import (
    OperationProxyBase,
    OperationViewProviderBase,
    RecordingOperationMixin,
    add_chop_properties,
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
        lines.extend(self.chop_lines(varname))
        return lines


class ExtrudeProxy(OperationProxyBase):
    """Proxy for a Part::FeaturePython object representing a classy_blocks Extrude."""

    FACE_LINKS = ("Base",)

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLink", "Base", "ClassyFoundry", "Face to extrude from"
        )
        obj.addProperty(
            "App::PropertyVector", "Amount", "ClassyFoundry", "Extrusion vector"
        ).Amount = FreeCAD.Vector(0, 0, 1)
        add_chop_properties(obj)

    def build_operation(self, obj, base_face):
        amount = [obj.Amount.x, obj.Amount.y, obj.Amount.z]
        return RecordingExtrude(base_face, amount, obj.Base.Name.lower())


class ExtrudeViewProvider(OperationViewProviderBase):
    """Minimal ViewProvider so the Extrude's Shape renders in the 3D view."""


def make_extrude(doc, name="Extrude"):
    """Create a new Extrude Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    ExtrudeProxy(obj)
    if FreeCAD.GuiUp:
        ExtrudeViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
