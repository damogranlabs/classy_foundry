"""Face profiles — flat 4-point quads, consumed by sweep operations (Extrude/Loft), not
added to the mesh themselves.

`FaceStep` is the shared marker base (so a sweep can `accept` any face source), with two
members: `Face` (corners entered/picked by hand) and `ExtractFace` (a face lifted off an
existing operation/shape by clicking it — `op.get_face(side)`, via a `FaceRef`).
"""

from .base import ProducingStep
from .faces import is_face_source


class FaceStep(ProducingStep):
    """Marker base for steps whose output is a classy_blocks Face (a sweep profile)."""

    adds_to_mesh = False
    category = ("Flat",)
    render_kind = "face"


class Face(FaceStep):
    cb_name = "Face"
    default_name = "face"
    label = "Face"
    SCHEMA = {
        "points": {
            "kind": "point_list",
            "label": "Points",
            "default": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        },
    }


class ExtractFace(FaceStep):
    """A face lifted off an existing operation/shape by clicking it: `name = op.get_face(side)`.
    The output is a reusable profile — feed it to Extrude/Loft, or connect it. A `FaceStep`
    (so sweeps accept it) but with its own build/codegen (the source is the picked face, not a
    `cb.Face(...)` constructor)."""

    default_name = "face"
    label = "Extract face"
    SCHEMA = {
        "face": {"kind": "face", "label": "Face", "default": None, "accepts": is_face_source},
    }

    def build(self, context):
        ref = self.values["face"]
        context[self] = ref.face(context) if ref is not None else None
        return context[self]

    def to_lines(self):
        ref = self.values["face"]
        return [f"{self.name} = {ref.face_expr()}"] if ref is not None else []
