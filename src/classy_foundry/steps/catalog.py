"""The catalog of implemented step types — the single place the add-step palette reads.

Adding a new step type to the palette = implement its class (with `category` + `label`)
and add it here. The palette groups these by `category` automatically; nothing else to
edit.
"""

from .box import Box
from .chop import Chop
from .extrude import Extrude
from .face import Face
from .mapped_sketch import MappedSketch
from .point import Point

CATALOG = [
    Point,
    Box,
    Extrude,
    Face,
    MappedSketch,
    Chop,
]
