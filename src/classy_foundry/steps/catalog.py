"""The catalog of implemented step types — the single place the add-step palette reads.

Adding a new step type to the palette = implement its class (with `category` + `label`)
and add it here. The palette groups these by `category`, preserving this list's order
(so order entries as they should appear in the menu — see design.md's palette layout).
"""

from .box import Box
from .chop import Chop
from .connector import Connector
from .curve import PointsFileCurve
from .edge import FACE_EDGES, OPERATION_EDGES
from .extrude import Extrude
from .face import ExtractFace, Face
from .graders import FixedCount, Inflation, Simple
from .loft import Loft
from .mapped_sketch import MappedSketch
from .optimize import (
    CurveClamp,
    FreeClamp,
    LineClamp,
    Optimize,
    PlaneClamp,
    RadialClamp,
    SketchOptimizer,
)
from .patch import SetPatch
from .point import OnCurvePoint, Point
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
from .surface import Surface
from .transform import Copy, Rotate, Scale, Translate
from .sketches import BoxedCircle, Circle, HalfCircle, OneCoreCircle, Oval
from .wedge import Wedge

CATALOG = [
    # References
    Point,
    PointsFileCurve,
    OnCurvePoint,
    Surface,
    # Flat
    Face,
    ExtractFace,
    MappedSketch,
    # Flat / Add edge
    *FACE_EDGES,
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
    Connector,
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
    # Modifiers
    Copy,
    Translate,
    Rotate,
    Scale,
    # Optimizers
    SketchOptimizer,
    # Optimizers / Clamps
    FreeClamp,
    LineClamp,
    PlaneClamp,
    RadialClamp,
    CurveClamp,
    # Optimizers (run)
    Optimize,
    # Solids / Add edge
    *OPERATION_EDGES,
    # Grading
    Chop,
    # Grading / Automatic
    FixedCount,
    Simple,
    Inflation,
    # Patches
    SetPatch,
]
