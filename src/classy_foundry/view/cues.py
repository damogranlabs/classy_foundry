"""Visual cues: highlight what a tool's inputs point to, and the candidate under
consideration — the general pre/selection workflow (holds for every step type).

There is **no ambient viewport selection**: a bare click in normal mode selects nothing.
Highlighting is driven entirely by the step you are editing (`session["active"]`, set from the
step list). Each frame `update_cues` derives a set of `(element, role)` and draws each as a
reserved-name overlay structure (`"cue N"` — a space => never a step name / selection, like the
world triad), *after* `sync_display` so the cues survive its `remove_all_structures`.

Roles (colour + emphasis):
- **output** — the active step's own produced geometry (so you see what you're editing);
- **input** — every ancestor element the active step references (what the tool consumes);
- **focus** — the one input whose pick is currently armed (drawn stronger).

(Hover *preselection* was tried and dropped: the per-frame `ps.pick` flickered and blocked the
committing click, and the static highlighting above already reads clearly on its own.)

An *element* is a `Step` (highlight its whole output), a `FaceRef` (one face), or a literal
`("point", [x, y, z])`. Geometry is resolved from the cached build context and reuses
`display`'s primitives (`geometry_of`, `_quad_mesh`, `POINT_RADIUS`). A single face/point
renders as a filled glow (lifted toward the camera so it neither z-fights nor is occluded);
a whole solid renders as a wireframe outline, so many simultaneous highlights stay legible.
"""

import numpy as np
import polyscope as ps

from ..steps.base import resolve_value
from ..steps.faces import FaceRef, SIDES, operations_of
from ..steps.point import PointStep
from .display import POINT_RADIUS, _quad_mesh, axis_vectors, geometry_of

PREFIX = "cue "  # trailing space => reserved: never a step name / selection

OUTPUT, INPUT, FOCUS, AXIS = "output", "input", "focus", "axis"
COLORS = {
    OUTPUT: (0.35, 0.55, 1.0),      # active step's own output — calm blue
    INPUT: (0.30, 0.85, 0.40),      # what the active step consumes — green
    FOCUS: (1.0, 0.55, 0.0),        # the input being picked right now — orange
    AXIS: (1.0, 0.3, 0.9),          # a step's rotation/revolve axis (point + direction) — magenta
}
FILLED = {FOCUS}                    # a solid glow (single face/point); context roles outline
WIRE_RADIUS = 0.004                 # relative; the outline / curve highlight tube


# ---- geometry: an element -> (topology, data) from the cached build context ----

def _step_geometry(step, context):
    """A step's whole output geometry (shared with the renderers/scene-fit via `geometry_of`)."""
    value = context.get(step)
    return geometry_of(step, value) if value is not None else None


def _face_geometry(face_ref, context):
    value = context.get(face_ref.step)
    if value is None:
        return None
    op = operations_of(value)[face_ref.index // 6]
    return "quad", [op.get_face(SIDES[face_ref.index % 6]).point_array]


def _axis_geometry(step, context):
    """Resolve a step's declared axis (`AXIS = (origin_field, direction_field)`) to
    (origin, direction) coordinates via the same `resolve_value` the build uses; None if it
    doesn't resolve (mid-edit, unbuilt ref, …)."""
    origin_field, direction_field = step.AXIS
    try:
        origin = np.asarray(resolve_value(step.values[origin_field], step.SCHEMA[origin_field],
                                          context), float).ravel()
        direction = np.asarray(step.values[direction_field], float).ravel()
    except Exception:
        return None
    return ("axis", (origin, direction)) if origin.size == 3 == direction.size else None


_TUPLE = {  # a tuple element is (tag, …): a literal point, or an axis carried by its step
    "point": lambda e, context: ("cloud", [e[1]]),
    "axis": lambda e, context: _axis_geometry(e[1], context),
}


ELEMENTS = {
    FaceRef: _face_geometry,
    PointStep: _step_geometry,
    tuple: lambda element, context: _TUPLE[element[0]](element, context),
}


def _geometry(element, context):
    return ELEMENTS.get(type(element), _step_geometry)(element, context)


# ---- which elements to highlight, and in which role ----

def _field_elements(value, kind):
    extract = FIELD_ELEMENTS.get(kind)
    return extract(value) if extract else []


def _point_elements(entries):
    """A point entry is a `PointStep` (highlight its point output) or a literal [x, y, z]."""
    return [e if isinstance(e, PointStep) else ("point", e) for e in entries if e is not None]


FIELD_ELEMENTS = {  # schema kind -> field value -> [element, …]
    "ref": lambda v: [v] if v is not None else [],
    "point": lambda v: _point_elements([v]),
    "point_list": _point_elements,
    "face": lambda v: [v] if v is not None else [],
    "face_list": list,
}


def _highlights(model, session):
    """[(element, role), …] for the current frame: the active step's output and each of its
    inputs (the input whose pick is armed drawn as `focus`)."""
    out = []
    active = session.get("active")
    if active is None or active not in model.steps:
        return out
    out.append((active, OUTPUT))
    pick = session.get("pick")
    focus_field = pick[1] if pick and pick[0] is active else None
    for field, spec in active.SCHEMA.items():
        role = FOCUS if field == focus_field else INPUT
        out += [(element, role) for element in _field_elements(active.values[field], spec["kind"])]
    if active.AXIS:  # a step with an origin+direction axis (Revolve/Rotate) draws it as an arrow
        out.append((("axis", active), AXIS))
    return out


# ---- rendering ----

def _toward_camera(point):
    direction = np.asarray(ps.get_view_camera_parameters().get_position(), float) - point
    length = float(np.linalg.norm(direction))
    return direction / length if length else direction


def _lift(corners):
    """Nudge a face's corners toward the camera by a fraction of its size, so an opaque
    highlight sits just in front of the face (no z-fight, never occluded from either side)."""
    corners = np.asarray(corners, float)
    return corners + _toward_camera(corners.mean(axis=0)) * 0.01 * float(np.linalg.norm(corners[2] - corners[0]))


def _wire(arrays):
    """(nodes, edges) tracing the border of each quad — a wireframe outline of the element."""
    nodes, edges = [], []
    for corners in arrays:
        base = len(nodes)
        nodes.extend(np.asarray(corners, float).tolist())
        edges += [[base + i, base + (i + 1) % 4] for i in range(4)]
    return np.asarray(nodes), np.asarray(edges)


def _render_quad(name, arrays, color, filled):
    if filled and len(arrays) == 1:  # a single face -> solid glow lifted toward the camera
        mesh = ps.register_surface_mesh(name, *_quad_mesh([_lift(arrays[0])]))
        mesh.set_color(color)
        mesh.set_edge_width(1.0)
        return
    net = ps.register_curve_network(name, *_wire(arrays))  # a solid / context input -> outline
    net.set_color(color)
    net.set_radius(WIRE_RADIUS)


def _render_cloud(name, points, color, filled):
    cloud = ps.register_point_cloud(name, np.asarray(points, float).reshape(-1, 3))
    cloud.set_color(color)
    cloud.set_radius(1.5 * POINT_RADIUS)


def _render_curve(name, nodes, color, filled):
    net = ps.register_curve_network(name, np.asarray(nodes, float), "line")
    net.set_color(color)
    net.set_radius(WIRE_RADIUS)


def _render_axis(name, data, color, filled):
    """A point-and-vector axis: a small marker at the origin plus a scene-scaled direction
    arrow — the same ambient vector-quantity the world triad uses (`display.axis_vectors`)."""
    origin, direction = data
    length = float(np.linalg.norm(direction))
    unit = np.asarray(direction, float) / length if length else np.asarray(direction, float)
    cloud = ps.register_point_cloud(name, np.asarray([origin], float))
    cloud.set_color(color)
    cloud.set_radius(0.5 * POINT_RADIUS)
    axis_vectors(cloud, [("axis", unit, color)])


RENDER = {"quad": _render_quad, "cloud": _render_cloud, "curve": _render_curve, "axis": _render_axis}

_REMOVERS = ((ps.has_surface_mesh, ps.remove_surface_mesh),
             (ps.has_point_cloud, ps.remove_point_cloud),
             (ps.has_curve_network, ps.remove_curve_network))


def _clear(session):
    for name in session.get("cue_names", []):
        for present, remove in _REMOVERS:
            if present(name):
                remove(name)


def update_cues(model, session):
    """Draw the frame's highlights (see `_highlights`) as reserved-name overlay structures.
    Runs every frame after `sync_display`, so it survives rebuilds and tracks the active step,
    the armed pick, and the hover candidate without any ambient viewport selection."""
    _clear(session)
    context = session.get("context")
    names = []
    for element, role in _highlights(model, session):
        geometry = _geometry(element, context) if context is not None else None
        if geometry is None or geometry[1] is None:
            continue
        topology, data = geometry
        name = f"{PREFIX}{len(names)}"
        RENDER[topology](name, data, COLORS[role], role in FILLED)
        names.append(name)
    session["cue_names"] = names
