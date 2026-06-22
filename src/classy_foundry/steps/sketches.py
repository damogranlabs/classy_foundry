"""The flat-sketch catalogue — classy_blocks' ready-made disk/oval profiles.

Each is a pure `ProducingStep` declaration (`name = cb.SomeDisk(...)`). Like `Face`, a
sketch is a flat profile (`adds_to_mesh = False`) — consumed by the Shape operations, not
added to the mesh itself — and renders as the quad surface of its `.faces`.

`SketchStep` is the shared marker base, so a future Shape step can accept any sketch by
`accepts=SketchStep`. `DiskSketch` adds the `(center, radius point, normal)` schema the
round disks share; `WrappedDisk`/`Oval` declare their own.

Only classy_blocks' top-level-exported sketches are here. `QuarterDisk` and `Annulus`
(design's "Quarter circle"/"Ring") aren't in cb's public namespace yet, so they're absent
until cb exports them.
"""

from .base import ProducingStep


class SketchStep(ProducingStep):
    """Shared base for flat-sketch profiles (a marker for `accepts`, plus common attrs)."""

    adds_to_mesh = False
    category = ("Flat", "Sketches")
    render_kind = "sketch_faces"


class DiskSketch(SketchStep):
    """A round disk defined by centre, a point on the rim, and the plane normal."""

    SCHEMA = {
        "center_point": {"kind": "point", "label": "Center", "default": [0.0, 0.0, 0.0]},
        "radius_point": {"kind": "point", "label": "Radius point", "default": [1.0, 0.0, 0.0]},
        "normal": {"kind": "point3", "label": "Normal", "default": [0.0, 0.0, 1.0]},
    }


class Circle(DiskSketch):
    cb_name = "FourCoreDisk"
    default_name = "circle"
    label = "Circle"


class OneCoreCircle(DiskSketch):
    cb_name = "OneCoreDisk"
    default_name = "circle"
    label = "Circle (1 core)"


class HalfCircle(DiskSketch):
    cb_name = "HalfDisk"
    default_name = "half_circle"
    label = "Half circle"


class BoxedCircle(SketchStep):
    cb_name = "WrappedDisk"
    default_name = "boxed_circle"
    label = "Boxed circle"
    SCHEMA = {
        "center_point": {"kind": "point", "label": "Center", "default": [0.0, 0.0, 0.0]},
        "corner_point": {"kind": "point", "label": "Box corner", "default": [1.0, 1.0, 0.0]},
        "radius": {"kind": "float", "label": "Radius", "default": "0.5"},
        "normal": {"kind": "point3", "label": "Normal", "default": [0.0, 0.0, 1.0]},
    }


class Oval(SketchStep):
    cb_name = "Oval"
    default_name = "oval"
    label = "Oval"
    SCHEMA = {
        "center_point_1": {"kind": "point", "label": "Center 1", "default": [0.0, 0.0, 0.0]},
        "center_point_2": {"kind": "point", "label": "Center 2", "default": [2.0, 0.0, 0.0]},
        "normal": {"kind": "point3", "label": "Normal", "default": [0.0, 0.0, 1.0]},
        "radius": {"kind": "float", "label": "Radius", "default": "1.0"},
    }
