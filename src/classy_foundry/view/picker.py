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

    result = ps.pick(screen_coords=psim.GetMousePos())
    # The same click also drives Polyscope's own selection (set after this callback, so a
    # reset here won't stick). Record it as already-seen so the selection mirror won't move
    # the editor off the step being filled onto the picked one.
    session["last_selection"] = result.structure_name if result.is_hit else None
    picked = model.step_by_name(result.structure_name.split("::")[0]) if result.is_hit else None
    if picked is None or picked not in model.candidates(step, _accepts(step, field)):
        return False

    if kind == "face_list":
        return _pick_face(picked, result, step.values[field].append)
    if kind == "face":
        return _pick_face(picked, result, lambda ref: step.values.__setitem__(field, ref))
    if index is None:
        step.values[field] = picked
    else:
        step.values[field][index] = picked
    return True


def _pick_face(picked, result, place):
    """Hand a `FaceRef` for the hit face to `place` (append for a list, assign for one). A
    non-face hit (a vertex/edge) is ignored, so the user keeps clicking until a face lands."""
    data = result.structure_data
    if data.get("element_type") != "face" or data.get("index") is None:
        return False
    place(FaceRef(picked, data["index"]))
    return True
