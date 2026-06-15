"""Tier 2 'Loft' Document Object: a thin wrapper around classy_blocks' Loft."""

import classy_blocks as cb
import FreeCAD

from .recording import (
    OperationProxyBase,
    OperationViewProviderBase,
    RecordingOperationMixin,
    add_chop_patch_properties,
)


class RecordingLoft(RecordingOperationMixin, cb.Loft):
    """A cb.Loft that remembers its bottom/top Face varnames for codegen."""

    def __init__(self, bottom_face, top_face, bottom_varname, top_varname):
        self.bottom_varname = bottom_varname
        self.top_varname = top_varname
        super().__init__(bottom_face, top_face)
        self.referenced_faces = {bottom_varname: bottom_face, top_varname: top_face}

    def to_lines(self, varname: str) -> list[str]:
        lines = [f"{varname} = cb.Loft({self.bottom_varname}, {self.top_varname})"]
        lines.extend(self.chop_patch_lines(varname))
        return lines


class LoftProxy(OperationProxyBase):
    """Proxy for a Part::FeaturePython object representing a classy_blocks Loft."""

    FACE_LINKS = ("BottomFace", "TopFace")

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty("App::PropertyLink", "BottomFace", "ClassyFoundry", "Bottom face")
        obj.addProperty("App::PropertyLink", "TopFace", "ClassyFoundry", "Top face")
        add_chop_patch_properties(obj)

    def build_operation(self, obj, bottom_face, top_face):
        return RecordingLoft(
            bottom_face,
            top_face,
            obj.BottomFace.Name.lower(),
            obj.TopFace.Name.lower(),
        )


class LoftViewProvider(OperationViewProviderBase):
    """Minimal ViewProvider so the Loft's Shape renders in the 3D view."""


def make_loft(doc, name="Loft"):
    """Create a new Loft Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    LoftProxy(obj)
    if FreeCAD.GuiUp:
        LoftViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
