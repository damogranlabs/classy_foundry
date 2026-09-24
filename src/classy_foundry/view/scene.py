"""Renders a `Document` into Polyscope structures.

Three kinds of structure, no more: a point cloud of every point, one surface mesh carrying
every cell's sides, and one mesh per backdrop surface. Appearance (transparency, edges,
colours) is Polyscope's own business -- its structure controls already do all of it, so
none of it is written here.

A cell's sides are emitted as *independent* blocks of 8 (or 4) vertices rather than as a
shared vertex pool, so each block is visually and pickably its own thing.
"""

import os

import numpy as np
import polyscope as ps

from ..document import Document
from ..geom import load_trimesh

POINTS_NAME = "points"
CELLS_NAME = "blocks"
GIZMO_NAME = "move axes"

POINT_RADIUS = 0.01  # relative to the scene's bounding box, like every Polyscope radius

SELECTED_COLOR = (0.95, 0.2, 0.2)
POINT_COLOR = (1.0, 0.55, 0.1)

CELL_COLOR = (0.55, 0.6, 0.68)
SELECTED_CELL_COLOR = (0.95, 0.35, 0.25)

# The move gizmo's world axes and their colours, dimmed when the constraint forbids them.
AXIS_COLORS = ((1.0, 0.25, 0.25), (0.3, 0.85, 0.3), (0.35, 0.5, 1.0))
DIM = 0.25
GIZMO_SPAN = 0.1  # of the scene's extent, each way from the move centroid

# blockMesh hexahedron sides, as indices into a cell's 8 points; a 4-point cell is its own
# single quad. Keyed by cell size so a cell renders without asking what it is.
CELL_SIDES = {
    8: ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)),
    4: ((0, 1, 2, 3),),
}


def hex_faces(cells: list) -> tuple:
    """`(vertices, faces)` for every cell's sides: each cell contributes its own points,
    so `faces` addresses the returned array directly."""
    vertices = [point.position for cell in cells for point in cell.points]
    faces = [
        [offset + corner for corner in side]
        for offset, cell in zip(np.cumsum([0] + [len(c.points) for c in cells]), cells)
        for side in CELL_SIDES[len(cell.points)]
    ]
    return (
        np.asarray(vertices, dtype=float).reshape(-1, 3),
        np.asarray(faces, dtype=int).reshape(-1, 4),
    )


def sync(document: Document, selection=(), move=None, cells=()) -> dict:
    """(Re)register every structure from the document's current state and return them by
    name. Selected points and selected `cells` are coloured differently; `move`, when one is
    live, gets the axis gizmo. The names are what the work plane uses to decide what it may
    cut."""
    positions = np.asarray([point.position for point in document.points], dtype=float).reshape(
        -1, 3
    )
    structures = {}
    cloud = ps.register_point_cloud(POINTS_NAME, positions)
    structures[POINTS_NAME] = cloud
    cloud.set_radius(POINT_RADIUS)
    cloud.add_color_quantity("selection", _point_colors(document.points, selection), enabled=True)

    vertices, faces = hex_faces(document.cells)
    blocks = ps.register_surface_mesh(CELLS_NAME, vertices, faces)
    blocks.add_color_quantity("selection", _cell_colors(document.cells, cells),
                              defined_on="faces", enabled=True)
    structures[CELLS_NAME] = blocks

    for patch in document.patches:
        structures.update(_sync_backdrop(patch))

    structures.update(_sync_gizmo(move, document.extent))
    return structures


def _point_colors(points: list, selection) -> np.ndarray:
    """One colour per point: the selection stands out, everything else is uniform."""
    selected = frozenset(selection)
    return np.asarray(
        [(SELECTED_COLOR if point in selected else POINT_COLOR) for point in points], dtype=float
    ).reshape(-1, 3)


def cell_owners(cells: list) -> list:
    """The cell each rendered face belongs to, in the order `hex_faces` emits them -- so a
    pick's face index says which block was clicked, with no extra bookkeeping."""
    return [cell for cell in cells for _ in CELL_SIDES[len(cell.points)]]


def _cell_colors(cells: list, selection) -> np.ndarray:
    """One colour per rendered face: the selected blocks stand out."""
    selected = frozenset(selection)
    return np.asarray(
        [(SELECTED_CELL_COLOR if cell in selected else CELL_COLOR) for cell in cell_owners(cells)],
        dtype=float,
    ).reshape(-1, 3)


def _sync_gizmo(move, extent: float) -> dict:
    """Three world axes through the move's centroid, drawn only while a move is live. An
    axis the constraint permits is bright, the rest are dim -- so a `Shift+Z` plane lights
    X and Y, an `X` constraint lights X alone, and a free move lights none."""
    ps.remove_curve_network(GIZMO_NAME, error_if_absent=False)
    for live in filter(None, [move]):
        centre, reach = live.centroid, extent * GIZMO_SPAN
        axes = np.eye(3) * reach
        nodes = np.concatenate([centre - axes, centre + axes])
        edges = np.asarray([[i, i + 3] for i in range(3)], dtype=int)
        gizmo = ps.register_curve_network(GIZMO_NAME, nodes, edges)
        gizmo.add_color_quantity(
            "axes", _axis_colors(live.constraint), defined_on="edges", enabled=True
        )
        return {GIZMO_NAME: gizmo}
    return {}


def _axis_colors(constraint) -> np.ndarray:
    return np.asarray(
        [
            np.asarray(color) * (1.0 if constraint.allows(axis) else DIM)
            for axis, color in zip(np.eye(3), AXIS_COLORS)
        ],
        dtype=float,
    )


def _sync_backdrop(patch) -> dict:
    """A patch's surface file, drawn as a reference mesh -- what points snap to and what
    the topology is built against. A patch without a surface, or one whose file has moved,
    contributes nothing: paths arrive by drag-and-drop, from the command line and from a
    text field, so a bad one must not raise on every frame."""
    for path in filter(os.path.exists, filter(None, [patch.surface])):
        mesh = load_trimesh(path)
        name = f"surface::{patch.name}"
        surface = ps.register_surface_mesh(name, mesh.vertices, mesh.faces)
        surface.set_transparency(0.5)
        return {name: surface}
    return {}
