"""Viewport picking to fill an input (a `ref` field or a `point` entry) from a step.

An input's dropper arms a pick by setting `session["pick"] = (step, field, index)` (index
is None for a single field). The next viewport click resolves it: the picked structure's
name maps back to its step (structures are registered under the step name; sketch
substructures are suffixed), and the step is bound if it is an *acceptable ancestor* for
that field — point inputs accept `Point`, a `ref` field accepts its `accepts`. Routing
through `model.candidates` enforces both the type and no-forward-reference. One click
ends pick mode either way.
"""

import polyscope as ps
import polyscope.imgui as psim

from ..steps.point import Point

LEFT_MOUSE = 0


def _accepts(step, field):
    spec = step.SCHEMA[field]
    return Point if spec["kind"] in ("point", "point_list") else spec.get("accepts")


def handle_pick(model, session):
    """Resolve an armed pick against the next viewport click; return True if bound."""
    target = session.get("pick")
    if target is None:
        return False
    if psim.GetIO().WantCaptureMouse or not psim.IsMouseClicked(LEFT_MOUSE):
        return False
    session["pick"] = None  # a single click resolves pick mode, hit or miss

    result = ps.pick(screen_coords=psim.GetMousePos())
    picked = model.step_by_name(result.structure_name.split("::")[0]) if result.is_hit else None
    step, field, index = target
    if picked is None or picked not in model.candidates(step, _accepts(step, field)):
        return False

    if index is None:
        step.values[field] = picked
    else:
        step.values[field][index] = picked
    return True
