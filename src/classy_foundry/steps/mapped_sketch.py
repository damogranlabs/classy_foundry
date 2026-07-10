"""'MappedSketch' step — a recipe for classy_blocks' MappedSketch (a 2D profile).

A profile, not added to the mesh itself; consumed by sweep operations. `positions` and
`quads` are the constructor's two args (so build()/to_lines()/pickle come for free). Points
are placed by picking world positions on existing geometry (the sketcher's picker-of-
everything), so a sketch needs no work plane of its own — it isn't required to be planar.
"""

from .base import eval_vec
from .sketches import SketchStep


class MappedSketch(SketchStep):
    cb_name = "MappedSketch"
    default_name = "sketch"
    category = ("Flat",)  # a top-level Flat item, not part of the disk catalogue
    label = "Mapped sketch"
    render_kind = "sketch"  # its own raw point/quad renderer (shows an in-progress sketch)
    SCHEMA = {
        "positions": {"kind": "point_list", "label": "Points", "default": []},
        "quads": {"kind": "index_list", "label": "Quads", "default": []},
    }

    @property
    def positions(self):
        return self.values["positions"]

    @property
    def quads(self):
        return self.values["quads"]

    def resolved_positions(self, params=None):
        """The raw positions as concrete `[x, y, z]` — each is a numeric list (a placed or
        snapshot point) or an expression string like `[bore/2, 0, 0]` (a parametric vertex,
        the sketch analogue of a parametric Point). A position that doesn't evaluate falls
        back to the origin, so the point indices its quads reference stay aligned while an
        expression is mid-edit. Used by the raw sketch render / overlay / number labels; the
        build itself resolves the same list through the `point_list` plumbing."""
        resolved = []
        for entry in self.positions:
            try:
                vec = eval_vec(entry, params)
                if len(vec) != 3:
                    raise ValueError("a point needs exactly three coordinates")
                resolved.append(vec)
            except Exception:
                resolved.append([0.0, 0.0, 0.0])
        return resolved
