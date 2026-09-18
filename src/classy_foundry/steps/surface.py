"""'STL surface' source — load an STL as a queryable `cb.TriangulatedSurface`.

Other steps *source data* from it (they reference it, `accepts=SurfaceStep`): a curve extracts a
cross-section (`surface.get_cross_sections(...)`), and a surface-snapping clamp finds closest
points (`surface.get_closest_point(...)`). It also shows in the viewport as a muted backdrop to
build against.

The mesh is read once (memoised by path in `geom.load_trimesh`) and wrapped in the cb surface at
build; codegen emits `cb.TriangulatedSurface.from_file(path)` so the exported script reads the
file itself. Earlier this step was display-only and emitted no script — it is now a real source
because cb gained a queryable `TriangulatedSurface`.
"""

import classy_blocks as cb

from ..geom import load_trimesh
from .base import ProducingStep


class SurfaceStep(ProducingStep):
    """Marker base for surface sources — the single 'is-a surface' truth, so any input that
    accepts a surface (a cross-section curve, a snapping clamp) accepts them all uniformly.
    Concrete surfaces add their cb wrapping."""

    render_kind = "surface"


class Surface(SurfaceStep):
    cb_name = "TriangulatedSurface"
    default_name = "surface"
    category = ("Sources",)
    label = "STL surface"
    SCHEMA = {
        "file": {"kind": "text", "label": "STL file", "default": ""},
    }

    def _construct(self, args):
        # wrap the cached (path-memoised) mesh — don't re-read the STL on every rebuild
        return cb.TriangulatedSurface(load_trimesh(args[0]))

    def _construct_expr(self, args_src):
        return f"cb.TriangulatedSurface.from_file({args_src})"
