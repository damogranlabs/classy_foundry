"""Reference curves built from data — currently the points-file curve.

`CurveStep` is the marker base (the single 'is-a curve' truth, e.g. for point-on-curve).
`PointsFileCurve` wraps `cb.LinearInterpolatedCurve`: it reads an (N, 3) point list from a
text file (the `points_file` kind) and interpolates a curve through it. The recipe stays a
tiny path — the points re-load on every build and in the exported script, so editing the
file flows through. Renders as a polyline (`"curve"`).
"""

import classy_blocks as cb

from .base import CODEGEN, ProducingStep, resolve_value
from .surface import SurfaceStep


class CurveStep(ProducingStep):
    """Marker base for reference curves — carries the shared `"curve"` render kind and is the
    type a point-on-curve (and future curve consumers) accept. Concrete curves add their cb
    wrapping."""

    render_kind = "curve"


class PointsFileCurve(CurveStep):
    cb_name = "LinearInterpolatedCurve"
    default_name = "curve"
    category = ("Sources",)
    label = "Points file"
    SCHEMA = {
        "points": {"kind": "points_file", "label": "Points file", "default": ""},
    }


class RevolvedProfile(CurveStep):
    """The meridian profile of a surface of revolution fitted to an STL:
    `name = cb.RevolvedSurface.from_file(path, axis, anchor).curve`. `axis` is the revolution
    direction; `anchor` is any off-axis point fixing the cutting plane and which side of the axis
    the profile is taken from. Being a `CurveStep`, cusp points / on-curve points ride it directly
    — so block vertices placed on its cusps follow the STL when its dimensions change (the payoff
    the cusp-point feature was built for). The surface object itself is not exposed yet; it is
    re-derived here purely to read `.curve` (add a Revolved *surface* step when snapping lands)."""

    cb_name = "RevolvedSurface"
    default_name = "profile"
    category = ("Sources",)
    label = "Revolved STL surface"
    render_kind = "revolved_surface"  # draws the loaded STL backdrop *and* the extracted profile
    SCHEMA = {
        "file": {"kind": "text", "label": "STL file", "default": ""},
        "axis": {"kind": "point3", "label": "Revolution axis", "default": [0.0, 0.0, 1.0]},
        "anchor": {"kind": "point", "label": "Anchor (off-axis)", "default": [1.0, 0.0, 0.0]},
    }

    def _construct(self, args):
        return cb.RevolvedSurface.from_file(*args).curve

    def _construct_expr(self, args_src):
        return f"cb.RevolvedSurface.from_file({args_src}).curve"


class CrossSectionCurve(CurveStep):
    """A curve cut from a surface source by a plane: `surface.get_cross_sections(origin, normal)`
    chained into one ordered path (`surface.sort_points(loops, far_point)`) and interpolated. The
    freeform sibling of `RevolvedProfile`: it references a `SurfaceStep` (so the cut follows the
    STL) instead of reading a path, since a snapping clamp will source the same surface. `origin`/
    `normal` place the cutting plane; `far_point` picks which end the path starts from (the seam),
    so the curve's direction is controllable. A `CurveStep`, so cusp points ride it directly."""

    default_name = "xsection"
    category = ("References",)
    label = "Curve from cross-section"
    SCHEMA = {
        "surface": {"kind": "ref", "label": "Surface", "default": None, "accepts": SurfaceStep},
        "origin": {"kind": "point", "label": "Plane origin", "default": [0.0, 0.0, 0.0]},
        "normal": {"kind": "point3", "label": "Plane normal", "default": [0.0, 0.0, 1.0]},
        "far_point": {"kind": "point", "label": "Start-from point", "default": [0.0, 0.0, 0.0]},
    }

    def build(self, context):
        surface = context[self.values["surface"]]
        origin, normal, far = (
            resolve_value(self.values[f], self.SCHEMA[f], context) for f in ("origin", "normal", "far_point")
        )
        points = surface.sort_points(surface.get_cross_sections(origin, normal), far)
        context[self] = cb.LinearInterpolatedCurve(points)
        return context[self]

    def to_lines(self):
        surface = self.values["surface"]
        name = surface.name if surface is not None else "None"
        origin, normal, far = (CODEGEN[self.SCHEMA[f]["kind"]](self.values[f]) for f in ("origin", "normal", "far_point"))
        return [
            f"{self.name} = cb.LinearInterpolatedCurve("
            f"{name}.sort_points({name}.get_cross_sections({origin}, {normal}), {far}))"
        ]
