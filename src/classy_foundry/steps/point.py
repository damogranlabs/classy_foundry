"""'Single point' step — a named reference coordinate: `name = [x, y, z]`.

Holds a fixed position that other steps can reference (a revolve origin/axis, a face
corner, …). classy_blocks has no public Point class, so it codegens as a plain
coordinate literal — which is exactly how hand-written scripts use reference points.
"""

from .base import ValueStep


class Point(ValueStep):
    default_name = "point"
    category = ("References",)
    label = "Single point"
    render_kind = "point"
    SCHEMA = {
        "position": {"kind": "point3", "label": "Position", "default": [0.0, 0.0, 0.0]},
    }
