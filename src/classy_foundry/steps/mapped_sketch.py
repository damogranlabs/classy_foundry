"""'MappedSketch' step — a recipe for classy_blocks' MappedSketch (a 2D profile).

A profile, not added to the mesh itself; consumed by sweep operations. `positions` and
`quads` are the constructor's two args (so build()/to_lines()/pickle come for free). Points
are placed by picking world positions on existing geometry (the sketcher's picker-of-
everything), so a sketch needs no work plane of its own — it isn't required to be planar.
"""

import numpy as np

from .base import _is_ref, eval_vec
from .sketches import SketchStep


def _resolved_coord(entry, context):
    """One `positions` entry -> an `[x, y, z]` (or None). A point *reference* (`PointStep`)
    resolves through the build `context` (so a sketch vertex follows the point it names), yielding
    None while its ancestor hasn't built. A literal / expression string evaluates in the params
    namespace (`[bore/2, 0, 0]` reads `bore` from `context.params`), yielding None while it's a
    mid-edit expression that doesn't parse. None lets display callers skip that vertex while the
    rest of the sketch still shows."""
    if _is_ref(entry):
        value = context.get(entry) if context is not None else None
        return None if value is None else [float(x) for x in np.asarray(value).ravel()]
    try:
        return eval_vec(entry, context.params if context is not None else None)
    except Exception:
        return None


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

    def resolved_positions(self, context):
        """The stored entries as `[x, y, z]` coordinates (None for one that can't resolve yet),
        index-aligned with `positions`/`quads` — the display's single source of vertex coordinates.
        An entry may be a point *reference* (follows the named point), an expression string
        (`[bore/2, 0, 0]`, resolved through `context.params`), or a plain literal; the build itself
        resolves the same list through the `point_list` plumbing."""
        return [_resolved_coord(entry, context) for entry in self.positions]
