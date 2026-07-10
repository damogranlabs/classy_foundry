"""The stack family — classy_blocks' stacks: a flat sketch swept into several stacked tiers.

A stack is the multi-tier sibling of a shape: same "sweep a sketch" idea, but repeated into
`repeats` layers, yielding a solid made of `repeats` tiers of operations. So each is a pure
`ProducingStep` declaration (`name = cb.SomeStack(sketch, …)`) that `adds_to_mesh`, and it
renders/patch-picks through the shared `"shape"` path — a `Stack` exposes `.operations`
(flattened over its tiers), which is all `operations_of` needs.

classy_blocks exports `ExtrudedStack` and `RevolvedStack`; there is no `LoftedStack` (only the
`TransformedStack` base), so — like the absent catalogue solids — it is simply not offered.
Grading is a manual `Chop` and/or an auto-grader, exactly as for shapes.
"""

from .base import ProducingStep
from .sketches import SketchStep


class StackStep(ProducingStep):
    """Shared base for swept multi-tier stacks."""

    adds_to_mesh = True
    category = ("Solids", "Stacks")
    render_kind = "shape"


class ExtrudedStack(StackStep):
    cb_name = "ExtrudedStack"
    default_name = "extruded_stack"
    label = "Extruded stack"
    SCHEMA = {
        "base": {"kind": "ref", "label": "Profile", "default": None, "accepts": SketchStep},
        "amount": {"kind": "float", "label": "Total height", "default": "1.0"},
        "repeats": {"kind": "int", "label": "Tiers", "default": "3"},
    }


class RevolvedStack(StackStep):
    cb_name = "RevolvedStack"
    default_name = "revolved_stack"
    label = "Revolved stack"
    SCHEMA = {
        "base": {"kind": "ref", "label": "Profile", "default": None, "accepts": SketchStep},
        "angle": {"kind": "float", "label": "Total angle (rad)", "default": "pi/2"},
        "axis": {"kind": "point3", "label": "Axis", "default": [0.0, 1.0, 0.0]},
        "origin": {"kind": "point", "label": "Origin", "default": [2.0, 0.0, 0.0]},
        "repeats": {"kind": "int", "label": "Tiers", "default": "3"},
    }
