"""Cusp markers + picking, shown only while a Cusp point step is being edited.

While `session["active"]` is a `CuspPoint`, the cusps of its selected curve are drawn as a
pickable point cloud (`f"{curve.name}::cusps"`), the bound one highlighted. A point-cloud pick
returns a bare point index (point clouds report no `element_type`) which the picker binds to the
step's `cusp` field — see `picker`. The marker order is exactly `find_cusps(threshold)` order, so a
picked index is the index the step re-resolves at build.

Like `cues`/`edges`, it's a reserved-name overlay re-registered every frame from the cached build
context, so it survives rebuilds and vanishes the moment another step is selected — no ambient
clutter, the same "highlighting is driven by the edited step" philosophy.
"""

import numpy as np
import polyscope as ps

from ..steps.base import eval_expr
from ..steps.point import CuspPoint

SUFFIX = "::cusps"  # reserved (like the ::points / ::edges overlays); never a bare step name
CUSP_RADIUS = 0.012
BASE_COLOR = (0.45, 0.8, 1.0)       # candidate cusp markers — cyan
HIGHLIGHT_COLOR = (1.0, 0.7, 0.25)  # the currently bound cusp — amber


def _clear(session):
    for name in session.get("cusp_names", []):
        if ps.has_point_cloud(name):
            ps.remove_point_cloud(name)


def _cusp_points(curve_value, threshold):
    """The cusp coordinates of a built curve, in `find_cusps` order (== the picked/built index)."""
    return np.asarray([cusp.point for cusp in curve_value.find_cusps(threshold)], float)


def draw_cusps(model, session):
    """Every frame: while a Cusp point step is active and its curve is built, register that curve's
    cusps as a pickable point cloud, the bound index highlighted. A no-op otherwise, so cusps show
    only while being edited."""
    _clear(session)
    names = []
    active = session.get("active")
    if isinstance(active, CuspPoint):
        context = session.get("context") or {}
        curve = active.values["curve"]
        value = context.get(curve)
        if value is not None:
            try:
                points = _cusp_points(value, eval_expr(active.values["threshold"], getattr(context, "params", {})))
            except Exception:
                points = np.empty((0, 3))  # a bad threshold / an unsupported curve: just show nothing
            if len(points):
                name = f"{curve.name}{SUFFIX}"
                cloud = ps.register_point_cloud(name, points)
                cloud.set_radius(CUSP_RADIUS)
                colors = np.tile(BASE_COLOR, (len(points), 1))
                bound = active.values["cusp"]
                if bound is not None and 0 <= bound < len(points):
                    colors[bound] = HIGHLIGHT_COLOR
                cloud.add_color_quantity("cusp", colors, enabled=True)
                names.append(name)
    session["cusp_names"] = names
