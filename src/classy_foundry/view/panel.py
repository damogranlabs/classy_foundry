"""The left panel: the single step list (with editable names + add palette) and Mesh
actions. The active step's editor is chosen by a type -> editor registry: a MappedSketch
gets the sketcher, everything else the generic schema-driven field editor.
"""

import polyscope.imgui as psim

from ..steps.catalog import CATALOG
from ..steps.mapped_sketch import MappedSketch
from ..steps.point import Point
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
    for name in sorted(part for part in node if part is not None):
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
    is_ref = isinstance(entry, Point)
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
    if not isinstance(new, Point):
        psim.SetNextItemWidth(-1)
        row_changed, xyz = psim.InputFloat3("##xyz", new)
        if row_changed:
            new, changed = list(xyz), True
    psim.PopID()
    return changed, new


def _point_field(step, field, spec, model, session):
    candidates = model.candidates(step, Point)
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


def _edit_field(step, field, spec, model, session):
    if spec["kind"] == "ref":
        return _ref_field(step, field, spec, model, session)
    if spec["kind"] in ("point", "point_list"):
        return _point_field(step, field, spec, model, session)
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


EDITORS = {MappedSketch: _sketch_editor}


def _draw_step_row(step, model, session):
    dirty = False
    psim.PushID(str(id(step)))
    if psim.SmallButton("^"):
        dirty |= model.move(step, -1)
    psim.SameLine()
    if psim.SmallButton("v"):
        dirty |= model.move(step, +1)
    psim.SameLine()
    psim.SetNextItemWidth(110)
    changed, new = psim.InputText("##name", step.name, max_str_len=64)
    if changed:
        model.rename(step, new)
    psim.SameLine()
    if psim.Selectable(type(step).__name__, session["active"] is step, size=(80, 0)):
        session["active"] = step
    psim.SameLine()
    if psim.SmallButton("x") and model.remove(step):
        if session["active"] is step:
            session["active"] = None
        dirty = True
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
    session["active"] = model.add(chosen())
    return True


def _draw_steps(model, sketch_editor, session):
    dirty = False
    for step in list(model.steps):
        dirty |= _draw_step_row(step, model, session)
    dirty |= _draw_palette(model, session)
    active = session["active"]
    if active is not None and active in model.steps:
        psim.Separator()
        dirty |= EDITORS.get(type(active), _generic_editor)(active, sketch_editor, model, session)
    return dirty


def _draw_mesh_actions(model, session):
    if psim.Button("Export script"):
        with open(SCRIPT_PATH, "w") as file:
            file.write(model.to_script())
    psim.SameLine()
    if psim.Button("Save"):
        model.save(MODEL_PATH)
    psim.SameLine()
    if psim.Button("Write blockMeshDict"):
        try:
            model.write_blockmesh(BLOCKMESH_PATH)
            session["status"] = f"Wrote {BLOCKMESH_PATH}"
        except Exception as error:
            session["status"] = f"Write failed: {type(error).__name__}: {error}"
    if session.get("status"):
        psim.TextUnformatted(session["status"])


def draw_panel(model, sketch_editor, session):
    """Draw the panel; return True if the viewport needs rebuilding."""
    dirty = False
    if session.get("pick") is not None:
        psim.TextUnformatted("Pick mode: click an item in the viewport (pick again to cancel)")
        psim.Separator()
    if psim.CollapsingHeader("Steps"):
        dirty |= _draw_steps(model, sketch_editor, session)
    if psim.CollapsingHeader("Mesh"):
        _draw_mesh_actions(model, session)
    return dirty
