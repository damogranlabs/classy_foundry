"""Tier 0 'PointListCurve' Document Object: a cb curve defined by a list of points."""

import classy_blocks as cb
import FreeCAD

from .recording import CurveProxyBase, ViewProviderBase

_CURVE_CLASSES = {
    "Discrete": cb.DiscreteCurve,
    "Linear": cb.LinearInterpolatedCurve,
    "Spline": cb.SplineInterpolatedCurve,
}

_CODEGEN_NAMES = {
    "Discrete": "cb.DiscreteCurve",
    "Linear": "cb.LinearInterpolatedCurve",
    "Spline": "cb.SplineInterpolatedCurve",
}


class RecordingPointListCurve:
    """Wraps a cb curve, remembers constructor args for codegen."""

    def __init__(self, points, curve_type, extrapolate, equalize):
        self._points_arg = [list(p) for p in points]
        self._curve_type = curve_type
        self._extrapolate = extrapolate
        self._equalize = equalize
        cls = _CURVE_CLASSES[curve_type]
        if curve_type == "Discrete":
            self._cb = cls(points)
        else:
            self._cb = cls(points, extrapolate, equalize)

    def discretize(self, count=50):
        if self._curve_type == "Discrete":
            return self._cb.discretize()
        return self._cb.discretize(count=count)

    def get_point(self, param):
        return self._cb.get_point(param)

    def get_closest_param(self, point):
        return self._cb.get_closest_param(point)

    def to_lines(self, varname):
        cls_name = _CODEGEN_NAMES[self._curve_type]
        pts = self._points_arg
        if self._curve_type == "Discrete":
            return [f"{varname} = {cls_name}({pts})"]
        return [
            f"{varname} = {cls_name}({pts}, extrapolate={self._extrapolate!r}, equalize={self._equalize!r})"
        ]


class PointListCurveProxy(CurveProxyBase):
    """Proxy for a Part::FeaturePython object representing a point-list-defined curve."""

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyPythonObject",
            "Points",
            "ClassyFoundry",
            "List of [x, y, z] points defining the curve",
        )
        obj.Points = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2, 1, 0]]

        obj.addProperty(
            "App::PropertyEnumeration",
            "CurveType",
            "ClassyFoundry",
            "Interpolation method between points",
        )
        obj.CurveType = list(_CURVE_CLASSES)
        obj.CurveType = "Linear"

        obj.addProperty(
            "App::PropertyBool",
            "Extrapolate",
            "ClassyFoundry",
            "Allow extrapolation beyond provided point bounds (interpolated types only)",
        )
        obj.addProperty(
            "App::PropertyBool",
            "Equalize",
            "ClassyFoundry",
            "Equalize parameter spacing by arc length (interpolated types only)",
        )
        obj.Equalize = True

    def build_curve(self, obj):
        points = obj.Points
        if not points or len(points) < 2:
            return None
        return RecordingPointListCurve(points, obj.CurveType, obj.Extrapolate, obj.Equalize)


class PointListCurveViewProvider(ViewProviderBase):
    """Minimal ViewProvider so the curve's wire renders in the 3D view."""


def make_point_list_curve(doc, name="Curve"):
    """Create a new PointListCurve Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    PointListCurveProxy(obj)
    if FreeCAD.GuiUp:
        PointListCurveViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
