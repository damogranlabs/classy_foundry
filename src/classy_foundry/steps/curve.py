"""Reference curves built from data — currently the points-file curve.

`CurveStep` is the marker base (the single 'is-a curve' truth, e.g. for point-on-curve).
`PointsFileCurve` wraps `cb.LinearInterpolatedCurve`: it reads an (N, 3) point list from a
text file (the `points_file` kind) and interpolates a curve through it. The recipe stays a
tiny path — the points re-load on every build and in the exported script, so editing the
file flows through. Renders as a polyline (`"curve"`).
"""

from .base import ProducingStep


class CurveStep(ProducingStep):
    """Marker base for reference curves — carries the shared `"curve"` render kind and is the
    type a point-on-curve (and future curve consumers) accept. Concrete curves add their cb
    wrapping."""

    render_kind = "curve"


class PointsFileCurve(CurveStep):
    cb_name = "LinearInterpolatedCurve"
    default_name = "curve"
    category = ("References",)
    label = "Curve from points"
    SCHEMA = {
        "points": {"kind": "points_file", "label": "Points file", "default": ""},
    }
