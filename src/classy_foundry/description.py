"""The handoff between the editor and classy_blocks, and its file format.

**This module belongs in classy_blocks** -- a `.shape` file is a classy_blocks document and
nobody should have to install foundry (and a GPU stack) to read one. It is written here
only until it is reviewed and moved, so it imports nothing from foundry:

    shape = cb.MappedShape(MappedShapeDescription.load("impeller.shape"))

Serialisation is stdlib: the on-disk shape *is* this dataclass -- plain lists, dicts and
numbers -- so `json` covers it. Each point, block and face is written on **one line**, so a
diff shows a moved point or a new block as a single changed row. Surfaces are written as
file paths relative to the `.shape` file, so a project directory stays movable.
"""

import json
import os
import re
from dataclasses import dataclass, field

import numpy as np
import trimesh

from classy_blocks.construct.surfaces.triangulated import TriangulatedSurface


class FileSurface(TriangulatedSurface):
    """A `TriangulatedSurface` that remembers the file it came from, so it can be written
    back out. Any other `SurfaceBase` (an analytic one, say) is usable in memory but
    cannot be saved -- the format references files."""

    def __init__(self, path: str) -> None:
        super().__init__(trimesh.load_mesh(path))
        self.path = os.path.abspath(path)


# An indented array of plain numbers, as `json.dump` leaves it: `[\n  1.0,\n  2.0\n ]`.
# Collapsing these -- and only these, since the character class excludes brackets -- puts one
# point, block or face per line while keeping the file valid JSON.
_NUMERIC_ARRAY = re.compile(r"\[\s+((?:-?[\d.eE+]+,?\s+)+)\]")


def _one_per_line(text: str) -> str:
    return _NUMERIC_ARRAY.sub(lambda match: "[" + " ".join(match.group(1).split()) + "]", text)


@dataclass
class MappedShapeDescription:
    # a list of points defining the whole shape
    points: np.ndarray
    # point connectivity; each block is represented by an 8-tuple (blockMesh vertex ordering)
    hexas: list
    # faces, defined here, belong to a patch
    patches: dict = field(default_factory=dict)
    # patch faces will be mapped to specified surfaces
    surfaces: dict = field(default_factory=dict)

    def save(self, path: str) -> None:
        """Write the `.shape` file."""
        base = os.path.dirname(os.path.abspath(path))
        content = {
            "points": np.asarray(self.points, dtype=float).reshape(-1, 3).tolist(),
            "hexas": [list(map(int, hexa)) for hexa in self.hexas],
            "patches": {name: [list(map(int, face)) for face in faces] for name, faces in self.patches.items()},
            "surfaces": {name: os.path.relpath(surface.path, base) for name, surface in self.surfaces.items()},
        }
        with open(path, "w") as handle:
            handle.write(_one_per_line(json.dumps(content, indent=1)) + "\n")

    @classmethod
    def load(cls, path: str) -> "MappedShapeDescription":
        base = os.path.dirname(os.path.abspath(path))
        with open(path) as handle:
            content = json.load(handle)
        return cls(
            points=np.asarray(content["points"], dtype=float).reshape(-1, 3),
            hexas=[list(hexa) for hexa in content["hexas"]],
            patches={name: [list(face) for face in faces] for name, faces in content["patches"].items()},
            surfaces={name: FileSurface(os.path.join(base, rel)) for name, rel in content["surfaces"].items()},
        )
