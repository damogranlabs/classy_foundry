"""Reference-point steps — named coordinates other steps (and clamps) can refer to.

`PointStep` is the marker base: the single 'is-a reference point' truth, so any input that
accepts a point — a Face corner, a revolve origin, later a clamp target — accepts all of
these uniformly. `Point` is a fixed coordinate literal; `OnCurvePoint` rides a curve at a
parameter. Both resolve to a plain coordinate, so the generic point-ref plumbing (resolve,
codegen, ref-extract) already handles them.
"""

from .base import CODEGEN, DerivedStep, Step, ValueStep, eval_expr
from .curve import CurveStep


class PointStep:
    """Marker: a step whose output is a reference coordinate. Mixed in alongside a build
    base (`ValueStep`, `DerivedStep`) so acceptance is one `isinstance(_, PointStep)` check."""


class Point(PointStep, ValueStep):
    """A fixed reference coordinate: `name = [x, y, z]`. classy_blocks has no Point class,
    so it codegens as a plain literal — exactly how hand-written scripts use reference points."""

    default_name = "point"
    category = ("Sources",)
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


class CuspPoint(PointStep, Step):
    """A reference point pinned to a curve's cusp (a sharp turn): the sibling of `OnCurvePoint`
    where the location isn't a typed parameter but a *picked* cusp. It resolves to
    `curve.find_cusps(threshold)[cusp].point`, re-found on every build — so when the curve
    changes (an edited points file today, an STL-extracted profile later) the point tracks the
    feature, not a frozen parameter. Indexing by position is safe while cusp count/order are
    stable (dimensions change, shape doesn't) — the `FaceRef`/`EdgeRef` see-and-fix contract.

    `curve` is the ordinary `ref` field (reused verbatim from `OnCurvePoint`); `threshold` a plain
    `float` (radians; an expression like `pi/6` works); `cusp` the one new field — the picked cusp
    index, filled by clicking a marker in the cusp overlay (see `view/cusps.py`, `picker`)."""

    default_name = "cusp_point"
    category = ("References",)
    label = "Cusp point"
    render_kind = "point"
    SCHEMA = {
        "curve": {"kind": "ref", "label": "Curve", "default": None, "accepts": CurveStep},
        "threshold": {"kind": "float", "label": "Angle threshold", "default": 0.5},
        "cusp": {"kind": "cusp", "label": "Cusp", "default": None, "accepts": CurveStep},
    }

    def build(self, context):
        curve = context[self.values["curve"]]
        cusps = curve.find_cusps(eval_expr(self.values["threshold"], context.params))
        context[self] = cusps[self.values["cusp"]].point
        return context[self]

    def to_lines(self):
        curve = self.values["curve"]
        name = curve.name if curve is not None else "None"
        threshold = CODEGEN["float"](self.values["threshold"])
        return [f"{self.name} = {name}.find_cusps({threshold})[{self.values['cusp']}].point"]
