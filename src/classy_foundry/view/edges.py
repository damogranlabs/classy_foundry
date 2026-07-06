"""Edge picking + indicators, shown only while an Edge step is being edited.

While `session["active"]` is an `EdgeStep`, the edges of every valid target are drawn as a
pickable curve network (a curve-network pick returns `element_type == "edge"` + a flat index
natively, so a click builds an `EdgeRef`/`FaceEdgeRef` — see `picker`). Which targets and how
they're wired depends on what the active step sets: an *operation* edge step lights up every
solid's block edges (eight corners × `EDGE_PAIRS`, with edge-chop marks); a *face* edge step
lights up every flat `Face`'s four edges. The valid targets are exactly `model.candidates` for
the step's target field, so the overlay and the pick accept the same things.

Each edge also shows a small glyph cluster: its `EdgeData` kind (nothing for a straight edge)
plus, on an operation, one mark per edge-chop (`operation.chop_edge`; faces have no chops).

Both are reserved-name overlays re-registered every frame from the cached build context (like
`cues`), so they survive rebuilds and vanish the moment another step is selected — no ambient
edge clutter, matching the cue philosophy that highlighting is driven by the edited step.
"""

import numpy as np
import polyscope as ps

from classy_blocks.util.tools import edge_map

from ..steps.edge import EdgeStep
from ..steps.faces import EDGE_PAIRS, faces_of, operations_of
from .display import operation_corners
from .labels import draw_clusters

PREFIX = "edges "  # trailing space => reserved: never a step name (like the cue overlay)
EDGE_RADIUS = 0.003

KIND_COLOR = (0.45, 0.8, 1.0)   # edge-data kind glyph — cyan
CHOP_COLOR = (1.0, 0.7, 0.25)   # edge-chop marks — amber
# EdgeData.kind -> a one-glyph indicator; unknown kinds fall back to their initial. An on-curve
# edge reports kind 'curve' whatever its representation, so one 'C' covers spline/polyLine both.
KIND_GLYPH = {"arc": "A", "origin": "O", "angle": "V", "project": "P", "curve": "C"}


def _kind_glyph(kind):
    return KIND_GLYPH.get(kind, kind[:1].upper()), KIND_COLOR


# ---- operation edges: eight corners per operation, twelve two-index edges, with chops ----

def _solid_network(value):
    """(nodes, edges) for one solid: each operation's eight corners, wired per `EDGE_PAIRS` in
    op-then-local order, so a picked edge index is `op * 12 + local` — the layout `EdgeRef` reads."""
    nodes, edges = [], []
    for op in operations_of(value):
        base = len(nodes)
        nodes.extend(operation_corners(op))
        edges.extend([base + corner_1, base + corner_2] for corner_1, corner_2 in EDGE_PAIRS)
    return np.asarray(nodes, float), np.asarray(edges, int)


def _edge_data(op, corner_1, corner_2):
    """The `EdgeData` stored on one edge of an operation (bottom/top face edge, or side edge),
    resolved through the same `edge_map` that `add_edge` uses."""
    location = edge_map[corner_1][corner_2]
    face = {"bottom": op.bottom_face, "top": op.top_face}.get(location.side)
    edges = face.edges if face is not None else op.side_edges
    return edges[location.start_corner]


def _solid_clusters(value):
    """[(corner_a, corner_b, glyphs), …] for one solid: each edge that has a non-straight kind
    and/or edge-chops contributes a glyph row (kind glyph first, then one `#` per chop)."""
    clusters = []
    for op in operations_of(value):
        corners = operation_corners(op)
        for corner_1, corner_2 in EDGE_PAIRS:
            glyphs = []
            kind = _edge_data(op, corner_1, corner_2).kind
            if kind != "line":
                glyphs.append(_kind_glyph(kind))
            chops = op.chops.edge_chops[corner_1][corner_2]
            glyphs += [("#", CHOP_COLOR)] * len(chops or [])
            if glyphs:
                clusters.append((corners[corner_1], corners[corner_2], glyphs))
    return clusters


# ---- face edges: four corners, four single-index edges, no chops (one face, or a sketch's many) ----

def _face_network(value):
    """(nodes, edges) for a flat value: each face's four corners wired in a loop, so a picked edge
    index is `face * 4 + corner` — the layout `FaceEdgeRef` reads. `faces_of` covers a bare Face
    (one face) and a sketch (its `.faces`) uniformly."""
    nodes, edges = [], []
    for face in faces_of(value):
        base = len(nodes)
        nodes.extend(face.point_array)
        edges.extend([base + i, base + (i + 1) % 4] for i in range(4))
    return np.asarray(nodes, float), np.asarray(edges, int)


def _face_clusters(value):
    """[(corner_a, corner_b, glyphs), …] for a flat value: each non-straight edge's kind glyph,
    across every face."""
    clusters = []
    for face in faces_of(value):
        corners = face.point_array
        clusters += [(corners[i], corners[(i + 1) % 4], [_kind_glyph(face.edges[i].kind)])
                     for i in range(4) if face.edges[i].kind != "line"]
    return clusters


# active step's target field kind -> (how to wire its edges, how to glyph them)
_SOURCES = {
    "edge": (_solid_network, _solid_clusters),
    "face_edge": (_face_network, _face_clusters),
}


def _source(active):
    """The (network, clusters) builders for the active step's target kind, or None if the active
    step doesn't set edges."""
    if not isinstance(active, EdgeStep):
        return None
    return _SOURCES.get(active.SCHEMA["target"]["kind"])


def _clear(session):
    for name in session.get("edge_names", []):
        if ps.has_curve_network(name):
            ps.remove_curve_network(name)


def draw_edges(model, session):
    """Every frame: while an Edge step is active, register the pickable edge network of each valid
    target (`model.candidates` for its target field) and draw the kind/chop glyph clusters. A
    no-op for any other active step, so edges show only while being edited."""
    _clear(session)
    names, clusters = [], []
    active = session.get("active")
    source = _source(active)
    if source is not None:
        network, cluster_glyphs = source
        context = session.get("context") or {}
        for step in model.candidates(active, active.SCHEMA["target"]["accepts"]):
            value = context.get(step)
            if value is None:
                continue
            name = f"{step.name}::edges"
            ps.register_curve_network(name, *network(value)).set_radius(EDGE_RADIUS)
            names.append(name)
            clusters += cluster_glyphs(value)
    session["edge_names"] = names
    draw_clusters(clusters)
