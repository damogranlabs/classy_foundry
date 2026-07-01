"""Transform steps — translate / rotate / scale any element in place.

classy_blocks gives one transform protocol to every element (`ElementBaseT`: operations,
shapes, sketches, faces), each method mutating in place and returning self — so these are
plain `ConfiguringStep`s (`<ref>.method(kwargs…)`, output = the moved target), no new
machinery. Field names match the cb parameter names, so they pass straight through as kwargs.

`origin` is a pickable `point` (default world origin) rather than cb's centroid default: it's
explicit, drives arrays/positioning (orbit about a shared axis), and reuses the dropper as a
pivot picker. A transform draws nothing itself — the target step renders the now-moved value.
"""

from .base import ConfiguringStep, DerivedStep
from .faces import is_face_source


def is_transformable(step) -> bool:
    """Any element classy_blocks can transform: a solid, shape, copy, sketch, or face profile."""
    return step.render_kind in ("operation", "shape", "element", "sketch", "sketch_faces", "face")


class Copy(DerivedStep):
    """Duplicate a solid into a new, independent element: `name = target.copy()`. The output
    is a fresh operation/shape added to the mesh — transform it without touching the original.
    `render_kind = "element"` because the copy's kind (operation vs shape) isn't known until
    built; one renderer handles both (see `view.display`)."""

    cb_method = "copy"
    category = ("Modifiers",)
    default_name = "copy"
    label = "Copy"
    adds_to_mesh = True
    render_kind = "element"
    SCHEMA = {
        "target": {"kind": "ref", "label": "Target", "default": None, "accepts": is_face_source},
    }


_TARGET = {"kind": "ref", "label": "Target", "default": None, "accepts": is_transformable}
_ORIGIN = {"kind": "point", "label": "Origin", "default": [0.0, 0.0, 0.0]}


class TransformStep(ConfiguringStep):
    category = ("Modifiers",)


class Translate(TransformStep):
    cb_method = "translate"
    default_name = "translate"
    label = "Translate"
    SCHEMA = {
        "target": _TARGET,
        "displacement": {"kind": "point3", "label": "By", "default": [1.0, 0.0, 0.0]},
    }


class Rotate(TransformStep):
    cb_method = "rotate"
    default_name = "rotate"
    label = "Rotate"
    AXIS = ("origin", "axis")  # draw the rotation axis as a point-and-vector cue
    SCHEMA = {
        "target": _TARGET,
        "angle": {"kind": "float", "label": "Angle (rad)", "default": "pi/2"},
        "axis": {"kind": "point3", "label": "Axis", "default": [0.0, 0.0, 1.0]},
        "origin": _ORIGIN,
    }


class Scale(TransformStep):
    cb_method = "scale"
    default_name = "scale"
    label = "Scale"
    SCHEMA = {
        "target": _TARGET,
        "ratio": {"kind": "float", "label": "Ratio", "default": "2.0"},
        "origin": _ORIGIN,
    }
