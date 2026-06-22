"""The catalog of implemented step types — the single place the add-step palette reads.

Adding a new step type to the palette = implement its class (with `category` + `label`)
and add it here. The palette groups these by `category`, preserving this list's order
(so order entries as they should appear in the menu — see design.md's palette layout).
"""

from .box import Box
from .chop import Chop
from .extrude import Extrude
from .face import Face
from .loft import Loft
from .mapped_sketch import MappedSketch
from .point import Point
from .revolve import Revolve
from .shapes import (
    Cylinder,
    EighthSphere,
    Elbow,
    ExtrudedRing,
    ExtrudedShape,
    Frustum,
    HalfSphere,
    LoftedShape,
    QuarterSphere,
    RevolvedRing,
    RevolvedShape,
)
from .sketches import BoxedCircle, Circle, HalfCircle, OneCoreCircle, Oval
from .wedge import Wedge

CATALOG = [
    # References
    Point,
    # Flat
    Face,
    MappedSketch,
    # Flat / Sketches catalogue
    HalfCircle,
    Circle,
    OneCoreCircle,
    Oval,
    BoxedCircle,
    # Solids / Simple
    Box,
    Extrude,
    Revolve,
    Loft,
    Wedge,
    # Solids / Shapes
    ExtrudedShape,
    RevolvedShape,
    LoftedShape,
    # Solids / Catalogue
    Cylinder,
    Frustum,
    Elbow,
    ExtrudedRing,
    RevolvedRing,
    EighthSphere,
    QuarterSphere,
    HalfSphere,
    # Grading
    Chop,
]
