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


def element_quads(value):
    """The side-quad point-arrays of every operation in a solid (bare op or multi-op shape).
    Shared with the cue overlay so a highlighted solid derives from the same geometry."""
    return [op.get_face(side).point_array for op in operations_of(value) for side in SIDES]


def operation_corners(op):
    """An operation's eight corner positions in classy_blocks' corner order (bottom face 0-3,
    top face 4-7) — the vertices its twelve block edges connect. Shared by the edge overlay and
    the cue highlight so both address edges by the same corner indices as `add_edge`."""
    return np.vstack([op.bottom_face.point_array, op.top_face.point_array])


def _render_element(step, context):
    """Any solid — operation, shape, or a copy of either — as the side quads of all its
    operations. `operations_of` unifies the single-op (a bare operation) and multi-op (a
    shape) cases, so one renderer covers all three render kinds."""
    value = context.get(step)
    if value is None:
        return
    mesh = ps.register_surface_mesh(step.name, *_quad_mesh(element_quads(value)))
    mesh.set_edge_width(1.0)  # show block borders by default (the Polyscope edge-width setting)


def _render_sketch(step, context):
    coords = step.resolved_positions(context)  # entries may be point refs; resolve to coordinates
    drawn = [c for c in coords if c is not None]
    if not drawn:
        return
    ps.register_point_cloud(points_cloud_name(step.name), np.asarray(drawn, float)).set_radius(POINT_RADIUS)
    if step.quads and None not in coords:  # quads need every vertex; skip while a ref is unbuilt
        mesh = ps.register_surface_mesh(f"{step.name}::quads",
                                        np.asarray(coords, float).reshape(-1, 3), np.asarray(step.quads, int))
        mesh.set_edge_width(1.0)  # show block borders by default (the Polyscope edge-width setting)


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


GEOMETRY = {  # render_kind -> (step, value) -> (topology, data); the geometry behind each renderer
    "operation": lambda s, v: ("quad", element_quads(v)),
    "shape": lambda s, v: ("quad", element_quads(v)),
    "element": lambda s, v: ("quad", element_quads(v)),
    "face": lambda s, v: ("quad", [v.point_array]),
    "sketch_faces": lambda s, v: ("quad", [f.point_array for f in v.faces]),
    "point": lambda s, v: ("cloud", [v]),
    "curve": lambda s, v: ("curve", v.discretize(count=CURVE_SAMPLES)),
    # cb reconstructs .positions from the faces (quad indices), so it needs ≥1 face; a quadless
    # in-progress sketch has none -> no cue cloud (the raw renderer still shows the loose points).
    "sketch": lambda s, v: ("cloud", np.asarray(v.positions) if v is not None and len(v.faces) else None),
}


def geometry_of(step, value):
    """(topology, data) for a step's output — the geometry the cue overlay and scene-fit share
    with the renderers, keyed by the same `render_kind`. None if the kind draws nothing."""
    extract = GEOMETRY.get(step.render_kind)
    return extract(step, value) if extract else None


def axis_vectors(cloud, arrows):
    """Attach true-length (`ambient`) direction arrows to a one-point cloud, scaled to the
    current scene extent — the shared triad/axis primitive. `arrows` = [(name, unit_dir, colour), …]."""
    length = 0.5 * ps.get_length_scale()
    for name, direction, colour in arrows:
        cloud.add_vector_quantity(name, np.asarray([direction], float) * length,
                                  vectortype="ambient", enabled=True, color=colour)


def _render_axes():
    """A world-origin triad (x=red, y=green, z=blue), sized to the current scene extent
    (`get_length_scale`) so it stays legible on any model."""
    cloud = ps.register_point_cloud(AXES_NAME, np.zeros((1, 3)))
    cloud.set_radius(POINT_RADIUS)
    axis_vectors(cloud, [(axis, colour, colour) for axis, colour in AXES])  # colour = unit dir


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
        overlay(context)  # the sketcher's markers resolve ref-valued vertices through the context
    return context  # stashed by the caller so cues can resolve element geometry between rebuilds
