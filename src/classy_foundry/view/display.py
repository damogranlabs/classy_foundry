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

from ..steps.faces import SIDES, operations_of  # canonical side order; face index i renders SIDES[i]

POINT_RADIUS = 0.02  # relative to scene extent; larger than Polyscope's tiny default

AXES_NAME = "world axes"  # a space => never a valid step name, so it can't collide / be picked
CURVE_SAMPLES = 100  # polyline resolution for a reference curve
AXES = (("x", (1.0, 0.0, 0.0)), ("y", (0.0, 1.0, 0.0)), ("z", (0.0, 0.0, 1.0)))  # colour = direction


def points_cloud_name(sketch_name):
    return f"{sketch_name}::points"


def _quad_mesh(point_arrays):
    """(vertices, quad_faces) from a list of 4-point arrays -- one quad each."""
    vertices, faces = [], []
    for corners in point_arrays:
        base = len(vertices)
        vertices.extend(np.asarray(corners, float).tolist())
        faces.append([base, base + 1, base + 2, base + 3])
    return np.asarray(vertices), np.asarray(faces)


def _render_element(step, context):
    """Any solid — operation, shape, or a copy of either — as the side quads of all its
    operations. `operations_of` unifies the single-op (a bare operation) and multi-op (a
    shape) cases, so one renderer covers all three render kinds."""
    value = context.get(step)
    if value is None:
        return
    arrays = [op.get_face(side).point_array for op in operations_of(value) for side in SIDES]
    ps.register_surface_mesh(step.name, *_quad_mesh(arrays))


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
    ps.register_surface_mesh(step.name, *_quad_mesh([value.point_array]))


def _render_sketch_faces(step, context):
    """A built sketch (Disk, Oval, …) draws as the quad surface of its `.faces`."""
    value = context.get(step)
    if value is None:
        return
    ps.register_surface_mesh(step.name, *_quad_mesh([face.point_array for face in value.faces]))


def _render_point(step, context):
    value = context.get(step)
    if value is None:
        return
    ps.register_point_cloud(step.name, np.asarray([value], float)).set_radius(POINT_RADIUS)


def _render_curve(step, context):
    """A reference curve draws as a polyline through its discretized points."""
    value = context.get(step)
    if value is None:
        return
    nodes = np.asarray(value.discretize(count=CURVE_SAMPLES), float)
    ps.register_curve_network(step.name, nodes, "line")


def _render_surface(step, context):
    """A reference STL: its triangles, muted and edge-free so it reads as a backdrop to build
    against, not as mesh output."""
    value = context.get(step)
    if value is None:
        return
    mesh = ps.register_surface_mesh(step.name, *value)
    mesh.set_color((0.7, 0.7, 0.75))
    mesh.set_edge_width(0.0)


def _render_nothing(step, context):
    """Steps with no own geometry (configuring steps like chop/patch) render nothing."""


RENDERERS = {
    "operation": _render_element,
    "shape": _render_element,
    "element": _render_element,  # a copy (operation or shape) — kind unknown until built
    "sketch": _render_sketch,
    "sketch_faces": _render_sketch_faces,
    "face": _render_face,
    "point": _render_point,
    "curve": _render_curve,
    "surface": _render_surface,
}


def _render_axes():
    """A fixed world-origin triad (x=red, y=green, z=blue) so axes/orientation are legible.
    Model-independent, so re-added on every rebuild rather than living in the overlay slot."""
    cloud = ps.register_point_cloud(AXES_NAME, np.zeros((1, 3)))
    cloud.set_radius(POINT_RADIUS)
    for axis, colour in AXES:
        cloud.add_vector_quantity(axis, np.asarray([colour], float), vectortype="ambient",
                                  enabled=True, color=colour)


def sync_display(model, overlay=None, upto=None, optimize=False):
    """Rebuild the viewport from the model prefix up to the rollback marker `upto`
    (a step; None = the whole list), then let an overlay re-add itself. `optimize` runs the
    (expensive) optimizer pass — set only for a one-shot Run, off for the live rebuild."""
    context = model.build(upto, optimize=optimize)
    ps.reset_selection()  # the selection points at structures we're about to replace
    ps.remove_all_structures()
    _render_axes()
    for step in model.prefix(upto):
        RENDERERS.get(step.render_kind, _render_nothing)(step, context)
    if overlay is not None:
        overlay()
