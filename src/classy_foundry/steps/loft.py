"""'Loft' step — a recipe for classy_blocks' Loft (a solid spanning two profiles).

The most general operation: sweeps a bottom Face to a top Face, interpolating the
sides. Both profiles are references to Face steps.
"""

from .base import ProducingStep
from .face import Face


class Loft(ProducingStep):
    cb_name = "Loft"
    default_name = "loft"
    adds_to_mesh = True
    category = ("Solids", "Simple")
    label = "Loft"
    render_kind = "operation"
    SCHEMA = {
        "bottom_face": {"kind": "ref", "label": "Bottom profile", "default": None, "accepts": Face},
        "top_face": {"kind": "ref", "label": "Top profile", "default": None, "accepts": Face},
    }
