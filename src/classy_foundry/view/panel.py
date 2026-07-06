"""The left panel: the single step list (with editable names + add palette) and Mesh
actions. The active step's editor is chosen by a type -> editor registry: a MappedSketch
gets the sketcher, everything else the generic schema-driven field editor.
"""

import polyscope.imgui as psim

from ..steps.catalog import CATALOG
from ..steps.mapped_sketch import MappedSketch
from ..steps.optimize import Optimize
from ..steps.point import PointStep
from .widgets import edit_field

MODEL_PATH = "model.pkl"
SCRIPT_PATH = "mesh_script.py"
BLOCKMESH_PATH = "blockMeshDict"


def _build_palette_tree(catalog):
    """Nest step classes into a menu tree by category path; leaves stored under key None."""
    tree = {}
    for step_class in catalog:
        node = tree
        for part in step_class.category:
            node = node.setdefault(part, {})
        node.setdefault(None, []).append(step_class)
    return tree


_PALETTE_TREE = _build_palette_tree(CATALOG)


def _render_palette_menu(node):
    """Render one menu level (submenus then leaf items); return the chosen class or None."""
    chosen = None
    for name in (part for part in node if part is not None):  # catalog order, not alphabetical
        if psim.BeginMenu(name):
            chosen = _render_palette_menu(node[name]) or chosen
            psim.EndMenu()
    for step_class in node.get(None, []):
        if psim.MenuItem(step_class.label or step_class.__name__):
            chosen = step_class
    return chosen


def _dropper(session, target):
    """Eyedropper button: toggle viewport-pick mode for `target` = (step, field, index).

    Arming pauses selection (app callback), so the next viewport click fills *this* input
    rather than selecting a step. Clicking it again cancels.
    """
    if psim.SmallButton("pick"):
        session["pick"] = None if session.get("pick") == target else target


def _ref_field(step, field, spec, model, session):
    candidates = model.candidates(step, spec.get("accepts"))
    current = step.values[field]
    changed = False
    psim.PushID(field)
    psim.TextUnformatted(spec["label"])
    psim.SetNextItemWidth(-44)  # leave room for the dropper
    if psim.BeginCombo("##ref", current.name if current is not None else "<none>"):
        for candidate in candidates:
            if psim.Selectable(candidate.name, candidate is current):
                step.values[field] = candidate
                changed = True
        psim.EndCombo()
    psim.SameLine()
    _dropper(session, (step, field, None))
    psim.PopID()
    return changed


def _point_entry(step, field, index, entry, candidates, session):
    """Render one point entry (literal [x,y,z] or a Point ref). Returns (changed, new).

    Layout stacks to fit any window width: a source combo (literal "(xyz)" vs a Point)
    plus a pick button on one line, then the xyz inputs filling the width below.
    """
    psim.PushID(f"{field}:{index}")
    changed = False
    new = entry
    is_ref = isinstance(entry, PointStep)
    if index is not None:
        psim.TextUnformatted(f"{index}")
        psim.SameLine()
    psim.SetNextItemWidth(-44)  # combo fills the row, leaving room for the pick button
    if psim.BeginCombo("##src", entry.name if is_ref else "(xyz)"):
        if psim.Selectable("(xyz)", not is_ref) and is_ref:
            new, changed = [0.0, 0.0, 0.0], True
        for candidate in candidates:
            if psim.Selectable(candidate.name, entry is candidate) and entry is not candidate:
                new, changed = candidate, True
        psim.EndCombo()
    psim.SameLine()
    _dropper(session, (step, field, index))
    if not isinstance(new, PointStep):
        psim.SetNextItemWidth(-1)
        row_changed, xyz = psim.InputFloat3("##xyz", new)
        if row_changed:
            new, changed = list(xyz), True
    psim.PopID()
    return changed, new


def _point_field(step, field, spec, model, session):
    candidates = model.candidates(step, PointStep)
    psim.TextUnformatted(spec["label"])
    if spec["kind"] == "point":
        changed, new = _point_entry(step, field, None, step.values[field], candidates, session)
        if changed:
            step.values[field] = new
        return changed
    changed = False
    entries = list(step.values[field])
    for i, entry in enumerate(entries):
        entry_changed, new = _point_entry(step, field, i, entry, candidates, session)
        if entry_changed:
            entries[i], changed = new, True
    if changed:
        step.values[field] = entries
    return changed


def _face_label(face):
    """Human-readable id of a picked face: 'cylinder · op2 · left' (a shape addresses its
    sub-operation) or 'box · top' (a bare operation)."""
    if face.step.render_kind == "shape":
        return f"{face.step.name} · op{face.index // 6} · {face.side()}"
    return f"{face.step.name} · {face.side()}"


def _face_list_field(step, field, spec, model, session):
    """A patch's faces: a toggle that arms accumulating viewport picks (see picker), plus the
    list of clicked faces, each removable. The picks themselves land in `handle_pick`."""
    psim.TextUnformatted(spec["label"])
    target = (step, field, None)
    armed = session.get("pick") == target
    if psim.Button("stop picking" if armed else "pick faces"):
        session["pick"] = None if armed else target
    faces = step.values[field]
    remove = None
    for i, face in enumerate(faces):
        psim.PushID(i)
        psim.TextUnformatted(_face_label(face))
        psim.SameLine()
        if psim.SmallButton("x"):
            remove = i
        psim.PopID()
    if remove is not None:
        faces.pop(remove)
        return True
    return False


def _face_field(step, field, spec, model, session):
    """A single picked face: a toggle that arms a one-shot viewport pick (see picker), then
    shows the face it landed on. Re-picking replaces it; 'x' clears it. `PushID(field)` keeps
    the per-field buttons distinct (two `face` fields, e.g. a Connector's, share labels)."""
    psim.PushID(field)
    psim.TextUnformatted(spec["label"])
    target = (step, field, None)
    armed = session.get("pick") == target
    current = step.values[field]
    if psim.Button("stop picking" if armed else "pick face"):
        session["pick"] = None if armed else target
    psim.SameLine()
    psim.TextUnformatted(_face_label(current) if current is not None else "<none>")
    changed = False
    if current is not None:
        psim.SameLine()
        if psim.SmallButton("x"):
            step.values[field] = None
            changed = True
    psim.PopID()
    return changed


def _edge_field(step, field, spec, model, session):
    """A single picked edge (an operation's or a flat face's — the ref describes itself): a toggle
    that arms a one-shot viewport pick (see picker), then shows the edge it landed on. Re-picking
    replaces it; 'x' clears it. Mirrors `_face_field`."""
    psim.PushID(field)
    psim.TextUnformatted(spec["label"])
    target = (step, field, None)
    armed = session.get("pick") == target
    current = step.values[field]
    if psim.Button("stop picking" if armed else "pick edge"):
        session["pick"] = None if armed else target
    psim.SameLine()
    psim.TextUnformatted(current.describe() if current is not None else "<none>")
    changed = False
    if current is not None:
        psim.SameLine()
        if psim.SmallButton("x"):
            step.values[field] = None
            changed = True
    psim.PopID()
    return changed


def _edit_field(step, field, spec, model, session):
    if spec["kind"] == "ref":
        return _ref_field(step, field, spec, model, session)
    if spec["kind"] in ("point", "point_list"):
        return _point_field(step, field, spec, model, session)
    if spec["kind"] == "face":
        return _face_field(step, field, spec, model, session)
    if spec["kind"] == "face_list":
        return _face_list_field(step, field, spec, model, session)
    if spec["kind"] in ("edge", "face_edge"):
        return _edge_field(step, field, spec, model, session)
    psim.PushID(field)
    psim.TextUnformatted(spec["label"])
    psim.SetNextItemWidth(-1)
    changed, new = edit_field(spec, step.values[field])
    if changed:
        step.values[field] = new
    psim.PopID()
    return changed


def _generic_editor(step, sketch_editor, model, session):
    dirty = False
    for field, spec in step.SCHEMA.items():
        dirty |= _edit_field(step, field, spec, model, session)
    return dirty


def _sketch_editor(step, sketch_editor, model, session):
    sketch_editor.activate(step)
    return sketch_editor.draw()


def _optimize_editor(step, sketch_editor, model, session):
    """The generic field editor plus a Run button: optimization is expensive and skipped on
    the live rebuild, so Run requests one `optimize`-mode rebuild on demand (see __main__)."""
    dirty = _generic_editor(step, sketch_editor, model, session)
    if psim.Button("Run"):
        session["run_optimize"] = True
        dirty = True
    return dirty


EDITORS = {MappedSketch: _sketch_editor, Optimize: _optimize_editor}


def _drag_handle(step, model):
    """Grab handle: hold and drag up/down to reorder, one swap per row-pitch crossed
    (the classic ImGui swap-on-cross idiom over `model.move`). A move blocked by the
    no-forward-reference guard simply doesn't reset the delta, so the drag *sticks* at the
    dependency wall — the guard rendered as felt resistance. Returns True if the list moved."""
    psim.SmallButton("::##drag")
    if psim.IsItemHovered():
        psim.SetTooltip("drag to reorder")
    if not psim.IsItemActive():
        return False
    dy = psim.GetMouseDragDelta(0)[1]
    pitch = psim.GetFrameHeightWithSpacing()
    if dy >= pitch and model.move(step, +1):
        psim.ResetMouseDragDelta()
        return True
    if dy <= -pitch and model.move(step, -1):
        psim.ResetMouseDragDelta()
        return True
    return False


def _draw_step_row(step, model, session, suspended):
    dirty = False
    psim.PushID(str(id(step)))
    if suspended:  # rows after the marker aren't built; grey them to show it
        psim.PushStyleColor(psim.ImGuiCol_Text, (0.5, 0.5, 0.5, 1.0))
    dirty |= _drag_handle(step, model)
    psim.SameLine()
    psim.SetNextItemWidth(110)
    changed, new = psim.InputText("##name", step.name, max_str_len=64)
    if changed:
        model.rename(step, new)
    psim.SameLine()
    if psim.Selectable(type(step).__name__, session["active"] is step, size=(80, 0)):
        session["active"] = step   # edit in context — selecting a step rolls the marker here too
        session["marker"] = step
        dirty = True
    psim.SameLine()
    if psim.SmallButton("x") and model.remove(step):
        if session["active"] is step:
            session["active"] = None
        if session.get("marker") is step:
            session["marker"] = None  # don't leave the marker pointing at a deleted step
        dirty = True
    if suspended:
        psim.PopStyleColor()
    psim.PopID()
    return dirty


def _draw_palette(model, session):
    if psim.Button("+ Add step"):
        psim.OpenPopup("add_step")
    chosen = None
    if psim.BeginPopup("add_step"):
        chosen = _render_palette_menu(_PALETTE_TREE)
        psim.EndPopup()
    if chosen is None:
        return False
    session["marker"] = None  # show the full model so the newly added step is visible
    session["active"] = model.add(chosen())
    return True


def _draw_steps(model, sketch_editor, session):
    dirty = False
    live = model.prefix(session.get("marker"))  # rows past the marker render greyed
    for step in list(model.steps):
        dirty |= _draw_step_row(step, model, session, step not in live)
    dirty |= _draw_palette(model, session)
    active = session["active"]
    if active is not None and active in model.steps:
        psim.Separator()
        dirty |= EDITORS.get(type(active), _generic_editor)(active, sketch_editor, model, session)
    return dirty


def _report(session, success, action, *args):
    """Run a file action, reporting its outcome on the status line; return whether it ran.
    The one place file errors (missing model, invalid mesh, …) are turned into feedback —
    so Save/Load/Export/Write all fail visibly instead of crashing the frame callback."""
    try:
        action(*args)
        session["status"] = success
        return True
    except Exception as error:
        session["status"] = f"Failed: {type(error).__name__}: {error}"
        return False


def _export_script(model):
    with open(SCRIPT_PATH, "w") as file:
        file.write(model.to_script())


def _reset_editing(model, sketch_editor, session):
    """Drop the editing cursors after a load: `active`/`marker`/`pick` (and the sketcher's
    own sketch handle) pointed at the steps the load just replaced. Land on the first step."""
    sketch_editor.activate(None)
    session["pick"] = session["marker"] = None
    session["active"] = model.steps[0] if model.steps else None


def _draw_mesh_actions(model, sketch_editor, session):
    """Persistence + output. The model path is editable, so several workflows live in named
    files; Save/Load round-trip the recipe (pickle). Returns True if the view must rebuild."""
    dirty = False
    session.setdefault("model_path", MODEL_PATH)
    psim.TextUnformatted("Model file")
    psim.SetNextItemWidth(-1)
    _, session["model_path"] = psim.InputText("##model_path", session["model_path"], max_str_len=256)
    path = session["model_path"]
    if psim.Button("Save"):
        _report(session, f"Saved {path}", model.save, path)
    psim.SameLine()
    if psim.Button("Load") and _report(session, f"Loaded {path}", model.load, path):
        _reset_editing(model, sketch_editor, session)
        dirty = True
    psim.Separator()
    if psim.Button("Export script"):
        _report(session, f"Wrote {SCRIPT_PATH}", _export_script, model)
    psim.SameLine()
    if psim.Button("Write blockMeshDict"):
        _report(session, f"Wrote {BLOCKMESH_PATH}", model.write_blockmesh, BLOCKMESH_PATH)
    if session.get("status"):
        psim.TextUnformatted(session["status"])
    return dirty


def draw_panel(model, sketch_editor, session):
    """Draw the panel; return True if the viewport needs rebuilding."""
    dirty = False
    if session.get("pick") is not None:
        psim.TextUnformatted("Pick mode: click an item in the viewport (pick again to cancel)")
        psim.Separator()
    if psim.CollapsingHeader("Steps"):
        dirty |= _draw_steps(model, sketch_editor, session)
    if psim.CollapsingHeader("Mesh"):
        dirty |= _draw_mesh_actions(model, sketch_editor, session)
    return dirty
