"""Edge steps — replace one edge's data (curve it, project it, grade its shape) via classy_blocks'
`add_edge` API, for both an operation's block edges and a flat face's edges.

An edge is straight by default; an edge step sets an `EdgeData` on one picked edge. The target is
an edge *reference* filled by clicking the viewport's edge overlay: an operation edge (`EdgeRef`,
two corners → `op.add_edge(c1, c2, data)`) or a flat-face edge (`FaceEdgeRef`, single corner →
`face.add_edge(corner, data)`). `EdgeStep` is blind to which — it just calls the ref's `apply_edge`
/ `add_edge_line` — so the two families are the *same* kinds pointed at different targets, and are
generated from one `_KINDS` table (no per-kind duplication, exactly the clamp-style type dispatch).

Curved edges are the single `OnCurve` kind: a spline/polyLine follows a reference curve (which
carries the through-points), so there are no inline point tables. There is no "line" kind — an edge
is straight until curved, and deleting the step restores that.

A step configures its target in place and produces nothing of its own (`render_kind = None`); the
target already shows, and the edge overlay draws the indicators while editing.
"""

import classy_blocks as cb

from .base import CODEGEN, Step, resolve_value
from .curve import CurveStep
from .face import Face
from .faces import is_face_source
from .mapped_sketch import MappedSketch


def _is_flat_edge_source(step) -> bool:
    """A step whose flat faces own their edges: a hand-built `Face`, or a `MappedSketch` (whose
    faces the user lays out by hand). Excludes `ExtractFace` (a non-conformal copy) and the disk
    catalogue (which generates its own rim curvature)."""
    return isinstance(step, (Face, MappedSketch))


class EdgeStep(Step):
    """Sets one edge's data: `<target>.add_edge(…, cb.X(args…))`.

    The `target` field (an edge reference) names the edge and its owner; every other schema field
    is a positional argument to the edge-data constructor (`edge_cls`), in order. Whether the owner
    is an operation or a flat face is entirely the reference's concern (`apply_edge`/`add_edge_line`).
    """

    edge_cls: str = ""
    default_name = "edge"
    render_kind = None

    def _arg_fields(self):
        return [(f, spec) for f, spec in self.SCHEMA.items() if f != "target"]

    def _data(self, context):
        args = [resolve_value(self.values[f], spec, context) for f, spec in self._arg_fields()]
        return getattr(cb, self.edge_cls)(*args)

    def build(self, context):
        self.values["target"].apply_edge(context, self._data(context))
        context[self] = None
        return None

    def to_lines(self):
        target = self.values["target"]
        if target is None:
            return []
        args = ", ".join(CODEGEN[spec["kind"]](self.values[f]) for f, spec in self._arg_fields())
        return [target.add_edge_line(f"cb.{self.edge_cls}({args})")]


_POINT = {"kind": "point", "default": [0.0, 0.0, 0.0]}

# Each edge kind, defined once: (cb class, palette label, its parameter fields after the target).
# Both families (operation edges, face edges) are generated from this — same kinds, different target.
_KINDS = [
    ("Arc", "Arc", {"arc_point": {**_POINT, "label": "Arc point"}}),
    ("Origin", "Origin", {"origin": {**_POINT, "label": "Origin"},
                          "flatness": {"kind": "float", "label": "Flatness", "default": "1"}}),
    ("Angle", "Angle", {"angle": {"kind": "float", "label": "Angle", "default": "pi/4"},
                        "axis": {"kind": "point3", "label": "Axis", "default": [0.0, 0.0, 1.0]}}),
    ("Project", "Project", {"label": {"kind": "text", "label": "Geometry", "default": "terrain"}}),
    ("OnCurve", "On curve", {"curve": {"kind": "ref", "label": "Curve", "default": None, "accepts": CurveStep},
                             "n_points": {"kind": "int", "label": "Points", "default": "10"},
                             "representation": {"kind": "choice", "label": "As", "default": "spline",
                                                "choices": ["spline", "polyLine"]}}),
]

# The two targets differ only in ref kind (which reference the pick builds) + what they accept + the
# label that tells the user what to click. Everything downstream is the same generated EdgeStep.
_OP_TARGET = {"kind": "edge", "label": "Operation edge", "default": None, "accepts": is_face_source}
_FACE_TARGET = {"kind": "face_edge", "label": "Face edge", "default": None, "accepts": _is_flat_edge_source}


def _family(prefix, target, category):
    """One EdgeStep subclass per kind, all sharing a target field + palette location. Bound to the
    module namespace so the pickled recipe can resolve each class by `edge.<Name>`."""
    family = []
    for edge_cls, label, params in _KINDS:
        name = f"{prefix}{edge_cls}Edge"
        cls = type(name, (EdgeStep,), {
            "__module__": __name__, "__qualname__": name,
            "edge_cls": edge_cls, "label": label, "category": category,
            "SCHEMA": {"target": target, **params},
        })
        globals()[name] = cls
        family.append(cls)
    return family


OPERATION_EDGES = _family("", _OP_TARGET, ("Solids", "Add edge"))
FACE_EDGES = _family("Face", _FACE_TARGET, ("Flat", "Add edge"))
