"""'MappedSketch' step — a recipe for classy_blocks' MappedSketch (a 2D profile).

A profile, not added to the mesh itself; consumed by sweep operations. `positions` and
`quads` are the constructor's two args (so build()/to_lines()/pickle come for free). The
work plane (origin + normal) is GUI-only metadata for placing viewport clicks — not a
constructor argument, so it lives outside `SCHEMA` but is still pickled.
"""

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

    def __init__(self, name="", **values):
        super().__init__(name, **values)
        self.work_origin = [0.0, 0.0, 0.0]
        self.work_normal = [0.0, 0.0, 1.0]

    @property
    def positions(self):
        return self.values["positions"]

    @property
    def quads(self):
        return self.values["quads"]
