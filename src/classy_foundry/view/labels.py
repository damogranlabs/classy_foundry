"""3D-anchored text labels, drawn as an ImGui overlay.

Polyscope has no native text/label quantity, so numbers that must sit *at* a world point
(sketch point indices, block-centre ids) are projected to screen coordinates each frame and
written with the ImGui foreground draw list. This is camera-dependent, so it runs every frame
from the app callback (like `cues`), not inside the rebuild.

Projection uses the view camera's own matrices, into ImGui screen space (`GetIO().DisplaySize`,
the same space `GetMousePos` / picking use), so a label lands exactly on its point.
"""

import numpy as np
import polyscope as ps
import polyscope.imgui as psim


def _world_to_screen(points):
    """Project world points to ImGui screen coords. Rows for points at/behind the camera are
    NaN so the caller skips them."""
    cam = ps.get_view_camera_parameters()
    view = np.asarray(cam.get_view_mat(), float)
    width, height = psim.GetIO().DisplaySize
    f = 1.0 / np.tan(np.radians(cam.get_fov_vertical_deg()) / 2.0)
    pts = np.asarray(points, float).reshape(-1, 3)
    eye = np.hstack([pts, np.ones((len(pts), 1))]) @ view.T
    w = -eye[:, 2]  # OpenGL eye space looks down -Z, so a visible point has w = -z_eye > 0
    screen = np.column_stack([((f / cam.get_aspect()) * eye[:, 0] / w * 0.5 + 0.5) * width,
                              (1.0 - (f * eye[:, 1] / w * 0.5 + 0.5)) * height])
    screen[w <= 0] = np.nan
    return screen


def draw_labels(entries, color):
    """Draw text at world points. `entries` = [(world_position, text), …]; `color` an RGB
    triple. Runs against the foreground draw list, so it overlays every structure."""
    if not entries:
        return
    screen = _world_to_screen([position for position, _ in entries])
    packed = psim.IM_COL32(*(int(255 * c) for c in color), 255)
    draw = psim.GetForegroundDrawList()
    for (x, y), (_, text) in zip(screen, entries):
        if not np.isnan(x):
            draw.AddText((float(x), float(y)), packed, text)


GLYPH_PITCH = 10.0  # px between successive glyphs in a cluster
EDGE_NUDGE = 12.0   # px the cluster sits off the edge line, so it never covers the pickable curve


def draw_clusters(clusters):
    """Draw a small row of glyphs at each edge. `clusters` = [(p_start, p_end, glyphs), …] with
    `glyphs` = [(text, rgb), …]; a cluster's row is centred on the edge midpoint, laid out along
    the edge's screen direction and nudged perpendicular so it sits beside the edge, not on it.
    A cluster whose edge is at/behind the camera is skipped (its endpoints project to NaN)."""
    flat = [point for start, end, _ in clusters for point in (start, end)]
    if not flat:
        return
    screen = _world_to_screen(flat)
    draw = psim.GetForegroundDrawList()
    for i, (_, _, glyphs) in enumerate(clusters):
        start, end = screen[2 * i], screen[2 * i + 1]
        if not glyphs or np.isnan(start[0]) or np.isnan(end[0]):
            continue
        along = end - start
        length = float(np.hypot(*along))
        along = along / length if length else np.array([1.0, 0.0])
        normal = np.array([-along[1], along[0]])
        origin = (start + end) / 2 + normal * EDGE_NUDGE - along * (GLYPH_PITCH * (len(glyphs) - 1) / 2)
        for j, (text, rgb) in enumerate(glyphs):
            x, y = origin + along * (GLYPH_PITCH * j)
            draw.AddText((float(x), float(y)), psim.IM_COL32(*(int(255 * c) for c in rgb), 255), text)
