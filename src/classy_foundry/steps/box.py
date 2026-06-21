"""'Box' step — a recipe for classy_blocks' Box (a 3D operation, added to the mesh)."""

from .base import ProducingStep


class Box(ProducingStep):
    cb_name = "Box"
    default_name = "box"
    adds_to_mesh = True
    category = ("Solids", "Simple")
    label = "Box"
    render_kind = "operation"
    SCHEMA = {
        "start_point": {"kind": "point", "label": "Corner", "default": [0.0, 0.0, 0.0]},
        "diagonal_point": {"kind": "point", "label": "Opposite corner", "default": [1.0, 1.0, 1.0]},
    }
