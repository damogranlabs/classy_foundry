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

from ..steps.faces import EdgeRef, FaceEdgeRef, FaceRef
from ..steps.point import PointStep

LEFT_MOUSE = 0

# A pick field's kind -> a resolver (picked_step, result) -> the value bound to the field, or None.
# Face/edge picks read a flat `data["index"]` off a curve-net/mesh hit (guarded by `element_type`)
# and wrap it in a lazily-resolving ref. A cusp reads a *point-cloud* hit's `data["index"]` (point
# clouds report no `element_type`) and binds the bare index — the curve is a separate `ref` field,
# so the index alone identifies the cusp. Adding a pickable element = one entry here.
def _solid_ref(element_type, ref_cls):
    def resolve(picked, result):
        data = result.structure_data
        if data.get("element_type") != element_type or data.get("index") is None:
            return None
        return ref_cls(picked, data["index"])
    return resolve


PICK_REFS = {
    "face": _solid_ref("face", FaceRef),
    "face_list": _solid_ref("face", FaceRef),
    "edge": _solid_ref("edge", EdgeRef),           # an operation's block edge
    "face_edge": _solid_ref("edge", FaceEdgeRef),  # a flat face's edge (curve-net pick, different ref)
    # a curve's cusp: the bare point index off the cusp *point-cloud* overlay. Guarding on the
    # Point Cloud type rejects a hit on the curve's own polyline (a Curve Network, which also
    # carries an index) — the cusp cloud is the only point cloud tied to a curve.
    "cusp": lambda picked, result: (
        result.structure_data.get("index") if result.structure_type_name == "Point Cloud" else None
    ),
}


def _accepts(step, field):
    spec = step.SCHEMA[field]
    return PointStep if spec["kind"] in ("point", "point_list") else spec.get("accepts")


def _resolve(model, target, result):
    """The value a pick `result` binds to for `target` = (step, field, index): a `FaceRef` for a
    `face`/`face_list` field, a cusp index for a `cusp` field, else the picked step — or None if
    the hit isn't an acceptable ancestor (type + no-forward-reference, via `model.candidates`) or
    the resolver rejects it. Shared by the click (`handle_pick`) and the hover preview."""
    step, field, _ = target
    picked = model.step_by_name(result.structure_name.split("::")[0]) if result.is_hit else None
    if picked is None or picked not in model.candidates(step, _accepts(step, field)):
        return None
    resolve = PICK_REFS.get(step.SCHEMA[field]["kind"])
    return resolve(picked, result) if resolve is not None else picked


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
    elif kind in ("face", "edge", "face_edge", "ref", "point", "cusp"):
        step.values[field] = element
    else:  # point_list entry
        step.values[field][index] = element
