"""Tier 1 'ExtractedFace' Document Object: a Face taken from one side of an Operation.

Unlike a plain Face (defined by 4 literal points), an ExtractedFace references
a Tier 2 Operation and one of its sides ('bottom', 'top', 'left', 'right',
'front', 'back') - e.g. the top face of an Extrude, ready to be chained into
the next operation. It generates `<source>.get_face('<side>')` rather than
re-specifying points.
"""

import classy_blocks as cb
import FreeCAD

from .recording import FaceProxyBase, ViewProviderBase, resolve_operation

SIDES = ("bottom", "top", "left", "right", "front", "back")


class RecordingExtractedFace(cb.Face):
    """A cb.Face extracted from one side of an Operation, remembering source+side for codegen."""

    def __init__(self, operation, source_varname, side):
        self.source_varname = source_varname
        self.side = side
        face = operation.get_face(side)
        super().__init__(face.point_array, edges=None)

    def to_lines(self, varname: str) -> list[str]:
        return [f"{varname} = {self.source_varname}.get_face({self.side!r})"]


class ExtractedFaceProxy(FaceProxyBase):
    """Proxy for a Part::FeaturePython object representing a Face extracted from an Operation."""

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLink", "Source", "ClassyFoundry", "Operation to extract the face from"
        )
        obj.addProperty(
            "App::PropertyEnumeration", "Side", "ClassyFoundry", "Side of Source to extract"
        )
        obj.Side = list(SIDES)

    def build_face(self, obj):
        operation = resolve_operation(obj.Source)
        if operation is None:
            return None
        return RecordingExtractedFace(operation, obj.Source.Name.lower(), obj.Side)


class ExtractedFaceViewProvider(ViewProviderBase):
    """Minimal ViewProvider so the ExtractedFace's Shape renders in the 3D view."""


def make_extracted_face(doc, source_obj, side, name="ExtractedFace"):
    """Create a new ExtractedFace Document Object in `doc`, extracting `side` of `source_obj`."""
    obj = doc.addObject("Part::FeaturePython", name)
    ExtractedFaceProxy(obj)
    obj.Source = source_obj
    obj.Side = side
    if FreeCAD.GuiUp:
        ExtractedFaceViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
