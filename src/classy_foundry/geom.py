"""Pure geometry helpers (no polyscope, no classy_blocks) -- unit-testable."""

import numpy as np


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
