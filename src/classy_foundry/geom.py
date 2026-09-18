"""Pure geometry helpers (no polyscope, no classy_blocks) -- unit-testable."""

import numpy as np
import trimesh

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
