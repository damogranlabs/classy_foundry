"""The solid-shape catalogue — classy_blocks' shapes built by sweeping a flat sketch.

Each is a pure `ProducingStep` declaration (`name = cb.SomeShape(sketch, …)`). A shape is
a 3D solid (`adds_to_mesh = True`) made of several operations, so it renders as the six
named sides of each operation in its `.operations`.

`ShapeStep` is the shared base (common attrs). The sketch input accepts any flat sketch
(`accepts=SketchStep`); like operations, a shape still needs grading before it can be
written (deferred).
"""

from .base import ProducingStep
from .face import FaceStep
from .sketches import SketchStep


class ShapeStep(ProducingStep):
    """Shared base for swept solid shapes."""

    adds_to_mesh = True
    category = ("Solids", "Shapes")
    render_kind = "shape"


class ExtrudedShape(ShapeStep):
    cb_name = "ExtrudedShape"
    default_name = "extruded_shape"
    label = "Extruded shape"
    SCHEMA = {
        "sketch": {"kind": "ref", "label": "Profile", "default": None, "accepts": SketchStep},
        "amount": {"kind": "float", "label": "Distance", "default": "1.0"},
    }


class RevolvedShape(ShapeStep):
    cb_name = "RevolvedShape"
    default_name = "revolved_shape"
    label = "Revolved shape"
    SCHEMA = {
        "sketch": {"kind": "ref", "label": "Profile", "default": None, "accepts": SketchStep},
        "angle": {"kind": "float", "label": "Angle (rad)", "default": "pi/2"},
        "axis": {"kind": "point3", "label": "Axis", "default": [0.0, 1.0, 0.0]},
        "origin": {"kind": "point", "label": "Origin", "default": [2.0, 0.0, 0.0]},
    }


class LoftedShape(ShapeStep):
    cb_name = "LoftedShape"
    default_name = "lofted_shape"
    label = "Lofted shape"
    SCHEMA = {
        "sketch_1": {"kind": "ref", "label": "Bottom profile", "default": None, "accepts": SketchStep},
        "sketch_2": {"kind": "ref", "label": "Top profile", "default": None, "accepts": SketchStep},
    }


# --- predefined round solids (catalogue): self-contained, built from points ---


class CatalogueShape(ShapeStep):
    """Shared attrs for the ready-made round solids (their own submenu)."""

    category = ("Solids", "Catalogue")


# Most round solids share the axis-and-radius idiom: a start/end axis point and a point
# on the start rim. Frustum/ring add an end/inner radius; the rest declare their own.
_AXIS_RADIUS = {
    "axis_point_1": {"kind": "point", "label": "Axis start", "default": [0.0, 0.0, 0.0]},
    "axis_point_2": {"kind": "point", "label": "Axis end", "default": [0.0, 0.0, 1.0]},
    "radius_point_1": {"kind": "point", "label": "Radius point", "default": [1.0, 0.0, 0.0]},
}


class Cylinder(CatalogueShape):
    cb_name = "Cylinder"
    default_name = "cylinder"
    label = "Cylinder"
    SCHEMA = dict(_AXIS_RADIUS)


class Frustum(CatalogueShape):
    cb_name = "Frustum"
    default_name = "frustum"
    label = "Conical frustum"
    SCHEMA = {**_AXIS_RADIUS, "radius_2": {"kind": "float", "label": "End radius", "default": "0.5"}}


class Elbow(CatalogueShape):
    cb_name = "Elbow"
    default_name = "elbow"
    label = "Elbow"
    SCHEMA = {
        "center_point_1": {"kind": "point", "label": "Center", "default": [0.0, 0.0, 0.0]},
        "radius_point_1": {"kind": "point", "label": "Radius point", "default": [1.0, 0.0, 0.0]},
        "normal_1": {"kind": "point3", "label": "Normal", "default": [0.0, 0.0, 1.0]},
        "sweep_angle": {"kind": "float", "label": "Sweep angle (rad)", "default": "pi/2"},
        "arc_center": {"kind": "point", "label": "Arc center", "default": [0.0, 2.0, 0.0]},
        "rotation_axis": {"kind": "point3", "label": "Rotation axis", "default": [0.0, 0.0, 1.0]},
        "radius_2": {"kind": "float", "label": "End radius", "default": "1.0"},
    }


class ExtrudedRing(CatalogueShape):
    cb_name = "ExtrudedRing"
    default_name = "extruded_ring"
    label = "Extruded ring"
    SCHEMA = {
        "axis_point_1": {"kind": "point", "label": "Axis start", "default": [0.0, 0.0, 0.0]},
        "axis_point_2": {"kind": "point", "label": "Axis end", "default": [0.0, 0.0, 1.0]},
        "outer_radius_point_1": {"kind": "point", "label": "Outer radius point", "default": [1.0, 0.0, 0.0]},
        "inner_radius": {"kind": "float", "label": "Inner radius", "default": "0.5"},
    }


class RevolvedRing(CatalogueShape):
    cb_name = "RevolvedRing"
    default_name = "revolved_ring"
    label = "Revolved ring"
    SCHEMA = {
        "axis_point_1": {"kind": "point", "label": "Axis start", "default": [0.0, 0.0, 0.0]},
        "axis_point_2": {"kind": "point", "label": "Axis end", "default": [0.0, 0.0, 1.0]},
        "cross_section": {"kind": "ref", "label": "Cross-section", "default": None, "accepts": FaceStep},
    }


class SphereShape(CatalogueShape):
    """Sphere octant/quadrant/hemisphere — all defined by centre, rim point, and normal."""

    SCHEMA = {
        "center_point": {"kind": "point", "label": "Center", "default": [0.0, 0.0, 0.0]},
        "radius_point": {"kind": "point", "label": "Radius point", "default": [1.0, 0.0, 0.0]},
        "normal": {"kind": "point3", "label": "Normal", "default": [0.0, 0.0, 1.0]},
    }


class EighthSphere(SphereShape):
    cb_name = "EighthSphere"
    default_name = "eighth_sphere"
    label = "Eighth sphere"


class QuarterSphere(SphereShape):
    cb_name = "QuarterSphere"
    default_name = "quarter_sphere"
    label = "Quarter sphere"


class HalfSphere(SphereShape):
    cb_name = "Hemisphere"
    default_name = "half_sphere"
    label = "Half sphere"
