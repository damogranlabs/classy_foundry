"""'MappedSketch' step — a recipe for classy_blocks' MappedSketch (a 2D profile).

A profile, not added to the mesh itself; consumed by sweep operations. `positions` and
`quads` are the constructor's two args (so build()/to_lines()/pickle come for free). The
work plane (origin + normal) is GUI-only metadata for placing viewport clicks — not a
constructor argument, so it lives outside `SCHEMA` but is still pickled.
"""

import numpy as np

from .base import _is_ref
from .sketches import SketchStep


def _resolved_coord(entry, context):
    """One `positions` entry -> an `[x, y, z]` (or None): a point *reference* resolves through the
    build `context` (so a sketch vertex follows the point it names); a literal passes through; a
    reference whose ancestor hasn't built yields None, so display callers can skip it while the rest
    of the sketch still shows."""
    if not _is_ref(entry):
        return [float(x) for x in entry]
    value = context.get(entry) if context is not None else None
    return None if value is None else [float(x) for x in np.asarray(value).ravel()]


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

    def resolved_positions(self, context):
        """The stored entries as `[x, y, z]` coordinates (None for a reference that hasn't built),
        index-aligned with `positions`/`quads` — the display's single source of vertex coordinates
        now that an entry may be a point reference, not just a literal."""
        return [_resolved_coord(entry, context) for entry in self.positions]
