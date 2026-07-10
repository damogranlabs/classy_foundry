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
    if not step.positions:
        return
    points = np.asarray(step.resolved_positions(context.params), float).reshape(-1, 3)
    ps.register_point_cloud(points_cloud_name(step.name), points).set_radius(POINT_RADIUS)
    if step.quads:
        mesh = ps.register_surface_mesh(f"{step.name}::quads", points, np.asarray(step.quads, int))
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


GEOMETRY = {  # render_kind -> (step, value, params) -> (topology, data); geometry behind each renderer
    "operation": lambda s, v, p: ("quad", element_quads(v)),
    "shape": lambda s, v, p: ("quad", element_quads(v)),
    "element": lambda s, v, p: ("quad", element_quads(v)),
    "face": lambda s, v, p: ("quad", [v.point_array]),
    "sketch_faces": lambda s, v, p: ("quad", [f.point_array for f in v.faces]),
    "point": lambda s, v, p: ("cloud", [v]),
    "curve": lambda s, v, p: ("curve", v.discretize(count=CURVE_SAMPLES)),
    # raw resolved positions (like the sketch renderer) so an in-progress/quad-less sketch still shows
    "sketch": lambda s, v, p: ("cloud", s.resolved_positions(p) or None),
}


def geometry_of(step, value, params=None):
    """(topology, data) for a step's output — the geometry the cue overlay and scene-fit share
    with the renderers, keyed by the same `render_kind`. `params` resolves a sketch's parametric
    vertices (ignored by the value-derived kinds). None if the kind draws nothing."""
    extract = GEOMETRY.get(step.render_kind)
    return extract(step, value, params) if extract else None


_BOUND_POINTS = {  # topology -> the (-1, 3) coordinates that geometry contributes to a fit
    "quad": lambda data: np.vstack([np.asarray(a, float).reshape(-1, 3) for a in data]),
    "cloud": lambda data: np.asarray(data, float).reshape(-1, 3),
    "curve": lambda data: np.asarray(data, float).reshape(-1, 3),
}


def model_bounds(model, upto=None):
    """Axis-aligned (low, high) over all built model geometry, or None if nothing is built.
    Excludes the triad/cue overlays, so a fit frames the model itself with no feedback loop."""
    context = model.build(upto)
    coords = []
    for step in model.prefix(upto):
        value = context.get(step)
        if value is None:
            continue
        geometry = geometry_of(step, value, context.params)
        if geometry is None or geometry[1] is None:
            continue
        topology, data = geometry
        extract = _BOUND_POINTS.get(topology)
        if extract is not None and len(data):
            coords.append(extract(data))
    if not coords:
        return None
    points = np.vstack(coords)
    low, high = points.min(axis=0), points.max(axis=0)
    if float(np.linalg.norm(high - low)) < 1e-9:  # a single point: give it a unit box
        low, high = low - 1.0, high + 1.0
    return low, high


DEFAULT_BOUNDS = (np.array([-1.0, -1.0, -1.0]), np.array([1.0, 1.0, 1.0]))


def pin_scene():
    """Take control of the scene extents so Polyscope stops re-fitting to the data on every
    rebuild — which made the triad/ground/camera scale lurch as geometry changed and collapse
    when empty. Pins a fixed default world and a quiet, grid-free shadow ground; `fit_view`
    re-pins to the model on demand (the Fit action)."""
    ps.set_automatically_compute_scene_extents(False)
    ps.set_bounding_box(*DEFAULT_BOUNDS)
    ps.set_length_scale(float(np.linalg.norm(DEFAULT_BOUNDS[1] - DEFAULT_BOUNDS[0])))
    ps.set_ground_plane_mode("shadow_only")


def fit_view(model, upto=None):
    """The Fit action: re-pin the world to the current model's bounds and reframe the camera.
    A no-op on an empty model, so the world can never collapse to nothing."""
    bounds = model_bounds(model, upto)
    if bounds is None:
        return
    low, high = bounds
    ps.set_bounding_box(low, high)
    ps.set_length_scale(float(np.linalg.norm(high - low)))
    ps.reset_camera_to_home_view()


def axis_vectors(cloud, arrows):
    """Attach true-length (`ambient`) direction arrows to a one-point cloud, scaled to the
    pinned scene — the shared triad/axis primitive. `arrows` = [(name, unit_dir, colour), …]."""
    length = 0.5 * ps.get_length_scale()
    for name, direction, colour in arrows:
        cloud.add_vector_quantity(name, np.asarray([direction], float) * length,
                                  vectortype="ambient", enabled=True, color=colour)


def _render_axes():
    """A world-origin triad (x=red, y=green, z=blue), sized to the pinned scene so it stays
    legible on any model and stops resizing as geometry is added/removed (see `pin_scene`)."""
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
        try:
            RENDERERS.get(step.render_kind, _render_nothing)(step, context)
        except Exception:
            pass  # one bad renderer (mid-edit expression, degenerate geometry) mustn't blank the rest
    if overlay is not None:
        overlay(context)  # the sketch overlay resolves its positions with the build's params
    return context  # stashed by the caller so cues can resolve element geometry between rebuilds
