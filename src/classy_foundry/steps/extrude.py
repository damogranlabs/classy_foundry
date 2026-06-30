"""'Extrude' step — a recipe for classy_blocks' Extrude (a Face swept into a solid)."""

from .base import ProducingStep
from .face import FaceStep


class Extrude(ProducingStep):
    cb_name = "Extrude"
    default_name = "extrude"
    adds_to_mesh = True
    category = ("Solids", "Simple")
    label = "Extrude"
    render_kind = "operation"
    SCHEMA = {
        "base": {"kind": "ref", "label": "Profile", "default": None, "accepts": FaceStep},
        "amount": {"kind": "float", "label": "Distance", "default": "1.0"},
    }
