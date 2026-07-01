"""'Revolve' step — a recipe for classy_blocks' Revolve (a Face swept around an axis).

Revolves the profile by `angle` (radians, right-hand rule) about `axis` through
`origin`. The axis is a direction vector (a literal `point3`); the origin is a position,
so it may reference a Point step.
"""

from .base import ProducingStep
from .face import FaceStep


class Revolve(ProducingStep):
    cb_name = "Revolve"
    default_name = "revolve"
    adds_to_mesh = True
    category = ("Solids", "Simple")
    label = "Revolve"
    render_kind = "operation"
    AXIS = ("origin", "axis")  # draw the revolve axis as a point-and-vector cue
    SCHEMA = {
        "base": {"kind": "ref", "label": "Profile", "default": None, "accepts": FaceStep},
        "angle": {"kind": "float", "label": "Angle (rad)", "default": "pi/2"},
        "axis": {"kind": "point3", "label": "Axis", "default": [0.0, 0.0, 1.0]},
        "origin": {"kind": "point", "label": "Origin", "default": [0.0, 0.0, 0.0]},
    }
