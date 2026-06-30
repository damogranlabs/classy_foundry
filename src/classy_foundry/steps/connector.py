"""'Connector' step — bridge two faces with a loft in one shot: `cb.Loft(faceA, faceB)`.

The fast path for intermediate geometry: instead of extracting two faces and lofting them
(three steps), click the two faces to connect and get the bridging block directly. Each face
is a single `face` pick (a `FaceRef`), resolved to its live `cb.Face` at build / to its
`op.get_face(side)` source at codegen.
"""

import classy_blocks as cb

from .base import Step
from .faces import is_face_source

_FACE = {"kind": "face", "default": None, "accepts": is_face_source}


class Connector(Step):
    adds_to_mesh = True
    category = ("Solids", "Simple")
    default_name = "connector"
    label = "Connector"
    render_kind = "operation"
    SCHEMA = {
        "bottom_face": {**_FACE, "label": "From face"},
        "top_face": {**_FACE, "label": "To face"},
    }

    def _faces(self):
        return self.values["bottom_face"], self.values["top_face"]

    def build(self, context):
        bottom, top = self._faces()
        if bottom is None or top is None:
            return None
        context[self] = cb.Loft(bottom.face(context), top.face(context))
        return context[self]

    def to_lines(self):
        bottom, top = self._faces()
        if bottom is None or top is None:
            return []
        return [f"{self.name} = cb.Loft({bottom.face_expr()}, {top.face_expr()})"]
