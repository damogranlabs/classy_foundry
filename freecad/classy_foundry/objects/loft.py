"""Tier 2 'Loft' Document Object: a thin wrapper around classy_blocks' Loft."""

import classy_blocks as cb
import FreeCAD

from .recording import (
    RecordingOperationMixin,
    add_chop_patch_properties,
    apply_chop_patch,
    loft_preview_shape,
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


class LoftProxy:
    """Proxy for a Part::FeaturePython object representing a classy_blocks Loft."""

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty("App::PropertyLink", "BottomFace", "ClassyFoundry", "Bottom face")
        obj.addProperty("App::PropertyLink", "TopFace", "ClassyFoundry", "Top face")
        add_chop_patch_properties(obj)

    def execute(self, obj):
        bottom_obj = obj.BottomFace
        top_obj = obj.TopFace
        if bottom_obj is None or top_obj is None:
            return
        for face_obj in (bottom_obj, top_obj):
            if not hasattr(face_obj.Proxy, "face"):
                face_obj.recompute(True)
        if not hasattr(bottom_obj.Proxy, "face") or not hasattr(top_obj.Proxy, "face"):
            return

        loft = RecordingLoft(
            bottom_obj.Proxy.face,
            top_obj.Proxy.face,
            bottom_obj.Name.lower(),
            top_obj.Name.lower(),
        )
        apply_chop_patch(obj, loft)
        self.operation = loft
        obj.Shape = loft_preview_shape(loft)

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class LoftViewProvider:
    """Minimal ViewProvider so the Loft's Shape renders in the 3D view."""

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


def make_loft(doc, name="Loft"):
    """Create a new Loft Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    LoftProxy(obj)
    if FreeCAD.GuiUp:
        LoftViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
