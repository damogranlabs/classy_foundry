"""Pure geometry helpers (no polyscope, no classy_blocks) -- unit-testable."""

from dataclasses import dataclass
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


def _unit(vector) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    return vector / np.linalg.norm(vector)


@dataclass
class Plane:
    """A constraint: the moved points stay in this plane. Free move is not a special case
    -- it is the plane through the selection whose normal is the camera direction."""

    origin: np.ndarray
    normal: np.ndarray

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
