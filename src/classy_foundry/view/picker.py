"""Viewport picking to fill an input (a `ref` field or a `point` entry) from a step.

An input's dropper arms a pick by setting `session["pick"] = (step, field, index)` (index
is None for a single field). The next viewport click resolves it: the picked structure's
name maps back to its step (structures are registered under the step name; sketch
substructures are suffixed), and the step is bound if it is an *acceptable ancestor* for
that field — point inputs accept `Point`, a `ref` field accepts its `accepts`. Routing
through `model.candidates` enforces both the type and no-forward-reference. One click
ends pick mode either way.

A **`face`** / **`face_list`** field picks a face (or several): the hit's face index
addresses it directly (an operation/shape renders its faces as side quads — see
`display`/`FaceRef`), so no dropdown is needed. A `face_list` *accumulates* (each click
appends, stays armed — patch authoring); a single `face` sets one and disarms (extract a
face, connect two).
"""

import polyscope as ps
import polyscope.imgui as psim

from ..steps.faces import FaceRef
from ..steps.point import PointStep

LEFT_MOUSE = 0


def _accepts(step, field):
    spec = step.SCHEMA[field]
    return PointStep if spec["kind"] in ("point", "point_list") else spec.get("accepts")


def _resolve(model, target, result):
    """The element a pick `result` binds to for `target` = (step, field, index): a `FaceRef`
    for a `face`/`face_list` field, else the picked step — or None if the hit isn't an
    acceptable ancestor (type + no-forward-reference, via `model.candidates`) or, for a face
    field, isn't a face. Shared by the click (`handle_pick`) and the hover preview."""
    step, field, _ = target
    picked = model.step_by_name(result.structure_name.split("::")[0]) if result.is_hit else None
    if picked is None or picked not in model.candidates(step, _accepts(step, field)):
        return None
    if step.SCHEMA[field]["kind"] not in ("face", "face_list"):
        return picked
    data = result.structure_data
    if data.get("element_type") != "face" or data.get("index") is None:
        return None
    return FaceRef(picked, data["index"])


def handle_pick(model, session):
    """Resolve an armed pick against the next viewport click; return True if bound.

    A `face_list` field *accumulates* (each hit appends a face, stays armed); every other
    field resolves a single value and disarms."""
    target = session.get("pick")
    if target is None:
        return False
    if psim.GetIO().WantCaptureMouse or not psim.IsMouseClicked(LEFT_MOUSE):
        return False
    step, field, index = target
    kind = step.SCHEMA[field]["kind"]
    if kind != "face_list":  # only a face_list keeps picking; everything else is single-shot
        session["pick"] = None
    element = _resolve(model, target, ps.pick(screen_coords=psim.GetMousePos()))
    if element is None:
        return False
    _bind(step, field, index, kind, element)
    return True


def _bind(step, field, index, kind, element):
    """Store the resolved `element` in the field: append for a `face_list`, assign for a
    single `face`/`ref`, or replace one entry of a `point_list`."""
    if kind == "face_list":
        step.values[field].append(element)
    elif kind in ("face", "ref", "point"):
        step.values[field] = element
    else:  # point_list entry
        step.values[field][index] = element
