"""'Wedge' step — a recipe for classy_blocks' Wedge (an axisymmetric single-cell slice).

Revolves the profile symmetrically by +/- angle/2 about the x-axis, for axisymmetric
cases. Auto-creates the wedge patches and a single cell in z, so it needs no chop on
that axis. Angle is in radians (default ~2 deg).
"""

from .base import ProducingStep
from .face import Face


class Wedge(ProducingStep):
    cb_name = "Wedge"
    default_name = "wedge"
    adds_to_mesh = True
    category = ("Solids", "Simple")
    label = "Wedge"
    render_kind = "operation"
    SCHEMA = {
        "face": {"kind": "ref", "label": "Profile", "default": None, "accepts": Face},
        "angle": {"kind": "float", "label": "Angle (rad)", "default": "deg2rad(2)"},
    }
