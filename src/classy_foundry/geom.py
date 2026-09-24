"""Pure geometry helpers (no polyscope) -- unit-testable.

Besides the ray/plane maths, this holds the **constraints** a move runs under and what each
one means by *snapping to a surface*. Snapping intersects the geometry here rather than
asking polyscope what is under the cursor: the point being dragged sits under the cursor
itself, so a pick would keep hitting it (or a block) instead of the reference surface, and
the point would jump between the surface and the free solution.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import trimesh

TOL = 1e-6  # direction comparisons: these are axis alignments, not measurements

_MESH_CACHE: dict = {}  # path -> trimesh.Trimesh; avoids re-reading on every rebuild


def load_trimesh(path):
    """Read a surface mesh (STL and any other format trimesh handles) into a `trimesh.Trimesh`.
    `force="mesh"` flattens a multi-body scene to one mesh. Memoised by path: a reference surface
    is loaded once, not on every dirty-edit rebuild — so a large STL doesn't stall the live edit
    (edit the file → restart to re-read, for now). Shared by the surface *source* (which wraps it
    in a `cb.TriangulatedSurface`) and the viewport backdrop renderer."""
    if path not in _MESH_CACHE:
        _MESH_CACHE[path] = trimesh.load(path, force="mesh")
    return _MESH_CACHE[path]


def ray_plane_hit(origin, direction, plane_origin, plane_normal):
    """World point where a ray meets a plane, or None if parallel / behind the camera."""
    origin = np.asarray(origin, float)
    direction = np.asarray(direction, float)
    plane_origin = np.asarray(plane_origin, float)
    plane_normal = np.asarray(plane_normal, float)

    denom = float(direction @ plane_normal)
    if abs(denom) < 1e-9:
        return None
    t = float((plane_origin - origin) @ plane_normal / denom)
    if t <= 0:
        return None
    return (origin + t * direction).tolist()


def surface_hit(origin, direction, meshes) -> Optional[np.ndarray]:
    """Where the ray first meets any of the reference meshes, or None if it misses them
    all. One cast per frame while snapping; trimesh builds its acceleration structure on
    the first call and reuses it afterwards."""
    origin = np.asarray(origin, dtype=float)
    hits = [point for mesh in meshes
            for point in mesh.ray.intersects_location([origin], [np.asarray(direction, dtype=float)])[0]]
    return min(hits, key=lambda point: np.linalg.norm(point - origin), default=None)


def nearest_on_segments(starts: np.ndarray, ends: np.ndarray, origin, direction) -> Optional[np.ndarray]:
    """The point on a set of segments closest to a ray.

    Segments, not their end points: a cross-section of a coarse mesh has few vertices, and
    snapping to those alone would make the cursor jump from corner to corner instead of
    sliding along the section."""
    origin, ray = np.asarray(origin, dtype=float), _unit(direction)
    spans = ends - starts
    offsets = starts - origin
    lengths = np.einsum("ij,ij->i", spans, spans)
    along = spans @ ray
    denominator = lengths - along**2
    # A segment parallel to the ray has no unique closest point; its start serves.
    fraction = np.divide(along * (offsets @ ray) - np.einsum("ij,ij->i", spans, offsets),
                         denominator, out=np.zeros(len(spans)), where=np.abs(denominator) > TOL)
    points = starts + np.clip(fraction, 0.0, 1.0)[:, None] * spans
    return _closest_to_ray(points, origin, ray)


def _closest_to_ray(points: np.ndarray, origin: np.ndarray, ray: np.ndarray) -> Optional[np.ndarray]:
    if not len(points):
        return None
    offsets = points - origin
    distances = np.linalg.norm(offsets - np.outer(offsets @ ray, ray), axis=1)
    return points[int(np.argmin(distances))]


def _unit(vector) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    return vector / np.linalg.norm(vector)


@dataclass
class Plane:
    """A constraint: the moved points stay in this plane. Free move is not a special case
    -- it is the plane through the selection whose normal is the camera direction."""

    origin: np.ndarray
    normal: np.ndarray
    # Cut sections live exactly as long as the constraint, which is what makes caching
    # them safe: a new constraint is built whenever the plane changes.
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    def from_ray(self, origin, direction) -> Optional[np.ndarray]:
        hit = ray_plane_hit(origin, direction, self.origin, self.normal)
        return None if hit is None else np.asarray(hit, dtype=float)

    def project(self, point) -> np.ndarray:
        point = np.asarray(point, dtype=float)
        normal = _unit(self.normal)
        return point - ((point - self.origin) @ normal) * normal

    def offset(self, distance: float) -> np.ndarray:
        """A typed number has no meaning inside a plane, so it moves nothing."""
        return np.zeros(3)

    def allows(self, direction) -> bool:
        """Can the move travel along `direction`? True for the axes lying in the plane.
        A camera-facing plane allows no world axis, which is what a free move means."""
        return bool(abs(_unit(self.normal) @ _unit(direction)) < TOL)

    def snap(self, origin, direction, meshes) -> Optional[np.ndarray]:
        """The point on the **cross-section** -- where this plane cuts the surface -- that
        the cursor is pointing nearest to. So dragging traces that section, instead of
        landing on a projection that is on the plane but off the surface.

        The section is cut once and kept: the plane is fixed for the life of a move, and
        cutting a large mesh every frame would not keep up."""
        segments = self._segments(meshes)
        return None if segments is None else nearest_on_segments(*segments, origin, direction)

    def _segments(self, meshes):
        """`(starts, ends)` of the section polylines, cut on first use."""
        for cached in filter(lambda value: value is not None, [self._cache.get("segments", None)]):
            return cached
        loops = [points for mesh in meshes for points in _cross_section(mesh, self.origin, self.normal)]
        pairs = [(loop[:-1], loop[1:]) for loop in loops if len(loop) > 1]
        segments = None if not pairs else (np.concatenate([start for start, _ in pairs]),
                                           np.concatenate([end for _, end in pairs]))
        self._cache["segments"] = segments
        return segments


@dataclass
class Axis:
    """A constraint: the moved points stay on this line."""

    origin: np.ndarray
    direction: np.ndarray

    def from_ray(self, origin, direction) -> Optional[np.ndarray]:
        """The point on this axis closest to the ray -- the standard closest-approach of two
        lines. None when the ray is parallel to the axis and there is no unique answer."""
        axis, ray = _unit(self.direction), _unit(direction)
        between = np.asarray(self.origin, dtype=float) - np.asarray(origin, dtype=float)
        alignment = axis @ ray
        denominator = 1.0 - alignment**2
        if abs(denominator) < 1e-9:
            return None
        along = (alignment * (ray @ between) - axis @ between) / denominator
        return self.origin + along * axis

    def project(self, point) -> np.ndarray:
        axis = _unit(self.direction)
        return self.origin + ((np.asarray(point, dtype=float) - self.origin) @ axis) * axis

    def offset(self, distance: float) -> np.ndarray:
        return distance * _unit(self.direction)

    def allows(self, direction) -> bool:
        """Can the move travel along `direction`? Only along the axis itself, either way."""
        return bool(abs(abs(_unit(self.direction) @ _unit(direction)) - 1.0) < TOL)

    def snap(self, origin, direction, meshes) -> Optional[np.ndarray]:
        """The surface point under the cursor, pulled back onto the axis -- so the move
        stays constrained while still following the surface."""
        hit = surface_hit(origin, direction, meshes)
        return None if hit is None else self.project(hit)


class FreePlane(Plane):
    """The unconstrained move: the plane through the selection facing the camera.

    It solves a ray like any plane, but **snaps to the surface itself** rather than to a
    section of it -- a free move should slide the point over the geometry, and the plane is
    only there to give the cursor a depth."""

    def snap(self, origin, direction, meshes) -> Optional[np.ndarray]:
        return surface_hit(origin, direction, meshes)


def _cross_section(mesh, origin, normal) -> list:
    """The polylines where a plane cuts a mesh; empty when it misses."""
    section = mesh.section(plane_origin=np.asarray(origin, dtype=float),
                           plane_normal=np.asarray(normal, dtype=float))
    if section is None:
        return []
    return [np.asarray(entity.discrete(section.vertices), dtype=float) for entity in section.entities]
