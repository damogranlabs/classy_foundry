"""The patch panel: names, face counts, surface files.

A patch is a name, the faces that carry it, and the surface its faces get mapped onto.
Surfaces usually arrive by dragging a file onto the window (or on the command line), which
names the patch after the file; this panel is for re-pointing one and for assigning faces.

A patch with a surface and no faces is a *backdrop* -- an STL loaded to build against --
which is why setting a surface is enough to make it appear in the viewport.
"""

import os

import polyscope.imgui as psim

FACE_SIZE = 4
MISSING_COLOR = (1.0, 0.4, 0.4, 1.0)
_entry: dict = {"name": "", "surface": {}}  # the panel's own text buffers, keyed by patch name


def draw(editor) -> bool:
    """Render the panel; True when the scene needs a resync."""
    changed = False
    psim.TextUnformatted("Patches")
    _, _entry["name"] = psim.InputText("##new", _entry["name"])
    psim.SameLine()
    if psim.Button("Add") and _entry["name"]:
        editor.document.add_patch(_entry["name"])
        _entry["name"] = ""
    for patch in editor.document.patches:
        changed |= _draw_patch(editor, patch)
    return changed


def _draw_patch(editor, patch) -> bool:
    changed = False
    psim.PushID(patch.name)
    psim.TextUnformatted(f"{patch.name}: {len(patch.faces)} face(s)")
    for missing in filter(lambda path: not os.path.exists(path), filter(None, [patch.surface])):
        psim.TextColored(MISSING_COLOR, f"surface not found: {missing}")
    _entry["surface"].setdefault(patch.name, patch.surface or "")
    _, _entry["surface"][patch.name] = psim.InputText("surface", _entry["surface"][patch.name])
    psim.SameLine()
    if psim.Button("Set"):
        patch.surface = _entry["surface"][patch.name] or None
        changed = True
    if psim.Button(f"Assign {FACE_SIZE} selected points"):
        changed |= _assign(editor, patch)
    psim.PopID()
    return changed


def _assign(editor, patch) -> bool:
    """Add the selection as a face. A wrong count is a no-op -- the selection survives so
    the user can keep clicking."""
    try:
        editor.document.assign_face(patch, editor.selection)
    except ValueError:
        return False
    editor.clear_selection()
    return True
