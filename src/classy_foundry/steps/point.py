"""Reference-point steps — named coordinates other steps (and clamps) can refer to.

`PointStep` is the marker base: the single 'is-a reference point' truth, so any input that
accepts a point — a Face corner, a revolve origin, later a clamp target — accepts all of
these uniformly. `Point` is a fixed coordinate literal; `OnCurvePoint` rides a curve at a
parameter. Both resolve to a plain coordinate, so the generic point-ref plumbing (resolve,
codegen, ref-extract) already handles them.
"""

from .base import DerivedStep, ValueStep
from .curve import CurveStep


class PointStep:
    """Marker: a step whose output is a reference coordinate. Mixed in alongside a build
    base (`ValueStep`, `DerivedStep`) so acceptance is one `isinstance(_, PointStep)` check."""


class Point(PointStep, ValueStep):
    """A fixed reference coordinate: `name = [x, y, z]`. classy_blocks has no Point class,
    so it codegens as a plain literal — exactly how hand-written scripts use reference points."""

    default_name = "point"
    category = ("References",)
    label = "Single point"
    render_kind = "point"
    SCHEMA = {
        "position": {"kind": "point3", "label": "Position", "default": [0.0, 0.0, 0.0]},
    }


class OnCurvePoint(PointStep, DerivedStep):
    """A reference point riding a curve at a parameter: `name = curve.get_point(param)`
    (param in [0, 1]). The curve is construction geometry only — the output is a plain
    coordinate, referenceable like any Single point (e.g. as a clamp target)."""

    cb_method = "get_point"
    default_name = "point"
    category = ("References",)
    label = "Point on curve"
    render_kind = "point"
    SCHEMA = {
        "curve": {"kind": "ref", "label": "Curve", "default": None, "accepts": CurveStep},
        "param": {"kind": "float", "label": "Parameter (0..1)", "default": "0.5"},
    }
