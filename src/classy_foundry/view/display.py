"""Viewport: render each step via a `render_kind` -> renderer registry.

`sync_display` builds the model once into a context {step: cb_value} and renders each
step according to its declared `render_kind` (so every operation type shares one
renderer, declared not coded). Operation/face steps render from their built value (the
six named sides are classy_blocks' patch orientations); sketch steps render from their
raw points/quads, so they show even while in-progress (unbuildable). A single rebuild
path wipes and re-registers everything, then lets an optional overlay (the editor's
markers) re-add itself.
"""

import numpy as np
import polyscope as ps

SIDES = ("bottom", "top", "left", "right", "front", "back")
POINT_RADIUS = 0.02  # relative to scene extent; larger than Polyscope's tiny default


def points_cloud_name(sketch_name):
    return f"{sketch_name}::points"


def operation_geometry(operation):
    """(vertices, quad_faces) for one operation -- one quad per named side."""
    vertices, faces = [], []
    for side in SIDES:
        corners = np.asarray(operation.get_face(side).point_array)
        base = len(vertices)
        vertices.extend(corners.tolist())
        faces.append([base, base + 1, base + 2, base + 3])
    return np.asarray(vertices), np.asarray(faces)


def _render_operation(step, context):
    value = context.get(step)
    if value is None:
        return
    vertices, faces = operation_geometry(value)
    ps.register_surface_mesh(step.name, vertices, faces)


def _render_sketch(step, context):
    if not step.positions:
        return
    points = np.asarray(step.positions, float).reshape(-1, 3)
    ps.register_point_cloud(points_cloud_name(step.name), points).set_radius(POINT_RADIUS)
    if step.quads:
        ps.register_surface_mesh(f"{step.name}::quads", points, np.asarray(step.quads, int))


def _render_face(step, context):
    value = context.get(step)
    if value is None:
        return
    ps.register_surface_mesh(step.name, np.asarray(value.point_array), np.array([[0, 1, 2, 3]]))


def _render_point(step, context):
    value = context.get(step)
    if value is None:
        return
    ps.register_point_cloud(step.name, np.asarray([value], float)).set_radius(POINT_RADIUS)


def _render_nothing(step, context):
    """Steps with no own geometry (configuring steps like chop/patch) render nothing."""


RENDERERS = {
    "operation": _render_operation,
    "sketch": _render_sketch,
    "face": _render_face,
    "point": _render_point,
}


def sync_display(model, overlay=None):
    """Rebuild the whole viewport from the model, then let an overlay re-add itself."""
    context = model.build()
    ps.reset_selection()  # the selection points at structures we're about to replace
    ps.remove_all_structures()
    for step in model.steps:
        RENDERERS.get(step.render_kind, _render_nothing)(step, context)
    if overlay is not None:
        overlay()
