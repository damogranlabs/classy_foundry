"""'Face' step — a recipe for classy_blocks' Face (a 4-point flat profile).

Points are entered manually (a point-list field); curved edges are a later addition.
A profile, not added to the mesh itself — consumed by sweep operations like Extrude.
"""

from .base import ProducingStep


class Face(ProducingStep):
    cb_name = "Face"
    default_name = "face"
    adds_to_mesh = False
    category = ("Flat",)
    label = "Face"
    render_kind = "face"
    SCHEMA = {
        "points": {
            "kind": "point_list",
            "label": "Points",
            "default": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        },
    }
