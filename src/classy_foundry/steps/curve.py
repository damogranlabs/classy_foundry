"""Reference curves built from data — currently the points-file curve.

`PointsFileCurve` is a `ProducingStep` wrapping `cb.LinearInterpolatedCurve`: it reads an
(N, 3) point list from a text file (the `points_file` kind) and interpolates a curve
through it. The recipe stays a tiny path — the points re-load on every build and in the
exported script, so editing the file flows through. Renders as a polyline (`"curve"`).
"""

from .base import ProducingStep


class PointsFileCurve(ProducingStep):
    cb_name = "LinearInterpolatedCurve"
    default_name = "curve"
    category = ("References",)
    label = "Points file"
    render_kind = "curve"
    SCHEMA = {
        "points": {"kind": "points_file", "label": "Points file", "default": ""},
    }
