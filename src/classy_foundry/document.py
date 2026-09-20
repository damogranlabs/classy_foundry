"""The edited topology as an object graph: points, cells and patches that reference each
other by *identity*. No indices live here — adding or deleting a point renumbers nothing
because there are no numbers. Indices exist only in `storage.py`, at the file boundary.

Coordinates are hints: `MappedShape` maps patch faces onto real surfaces and optimises
afterwards, so nothing here is precision geometry.
"""

import os
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

import numpy as np

CELL_SIZES = (4, 8)  # a quad (the MappedSketch case) or a hexahedron
FACE_SIZE = 4


@dataclass(eq=False)
class Point:
    """A vertex. `eq=False` so `==` is identity: two points at the same place are two
    points, and a point stays hashable despite holding an array."""

    position: np.ndarray


@dataclass(eq=False)
class Cell:
    """A hexahedron (8 points) or a quad (4), ordered as the user clicked them --
    blockMesh vertex ordering, which is the contract with `MappedShape`."""

    points: list

    def uses(self, points: frozenset) -> bool:
        return any(point in points for point in self.points)


@dataclass(eq=False)
class Patch:
    """A named boundary. `faces` identify it by four points each; `surface` is the path of
    the file its faces get mapped onto. A patch with a surface and no faces is a
    *backdrop* -- an STL loaded to build against; a patch with faces and no surface is a
    plain boundary."""

    name: str
    faces: list = field(default_factory=list)
    surface: Optional[str] = None


@dataclass
class Document:
    """Everything being edited."""

    points: list = field(default_factory=list)
    cells: list = field(default_factory=list)
    patches: list = field(default_factory=list)

    def add_point(self, position) -> Point:
        point = Point(np.asarray(position, dtype=float))
        self.points.append(point)
        return point

    def add_cell(self, points: Sequence[Point]) -> Cell:
        if len(points) not in CELL_SIZES:
            raise ValueError(f"A cell takes {' or '.join(map(str, CELL_SIZES))} points, got {len(points)}")
        cell = Cell(list(points))
        self.cells.append(cell)
        return cell

    def add_patch(self, name: str, surface: Optional[str] = None) -> Patch:
        patch = Patch(name, surface=surface)
        self.patches.append(patch)
        return patch

    @property
    def extent(self) -> float:
        """How big the model is, so speeds and sizes scale with it -- the gizmo's reach,
        panning, dollying. Never below 1.0, since a fresh document has no points at all."""
        positions = np.asarray([point.position for point in self.points], dtype=float).reshape(-1, 3)
        spans = positions.ptp(axis=0) if len(positions) else np.zeros(3)
        return float(max(spans.max(), 1.0))

    def patch(self, name: str) -> Optional[Patch]:
        return next((patch for patch in self.patches if patch.name == name), None)

    def surface_patch(self, path: str) -> Patch:
        """The patch carrying `path` as its surface, named after the file: `blade.stl` ->
        `blade`. Loading a surface again re-points that one patch rather than adding
        another, and a patch that already has faces simply gains the surface."""
        name = os.path.splitext(os.path.basename(path))[0]
        patch = self.patch(name) or self.add_patch(name)
        patch.surface = path
        return patch

    def assign_face(self, patch: Patch, points: Sequence[Point]) -> None:
        if len(points) != FACE_SIZE:
            raise ValueError(f"A face takes {FACE_SIZE} points, got {len(points)}")
        patch.faces.append(tuple(points))

    def delete_points(self, points: Iterable[Point]) -> None:
        """Remove points, and with them every cell and patch face that references one --
        the way deleting a vertex takes its faces with it."""
        doomed = frozenset(points)
        self.cells = [cell for cell in self.cells if not cell.uses(doomed)]
        for patch in self.patches:
            patch.faces = [face for face in patch.faces if doomed.isdisjoint(face)]
        self.points = [point for point in self.points if point not in doomed]

    def delete_cells(self, cells: Iterable[Cell]) -> None:
        """Remove cells only; their points are shared and stay."""
        doomed = frozenset(cells)
        self.cells = [cell for cell in self.cells if cell not in doomed]
