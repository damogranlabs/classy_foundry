"""What the editor can do, as data.

One table drives both dispatch (`editor.py` maps `action` to a method) and the help
window, so the two cannot drift apart. Adding an operation is one row.

Blender's grammar, with one deliberate departure: delete is `Delete`, not `X`, because `X`
already constrains a move to the X axis and the collision is confusing outside Blender's
strictly modal context.
"""

from dataclasses import dataclass

import polyscope.imgui as psim


@dataclass
class Binding:
    key: str
    label: str
    description: str
    action: str


BINDINGS = [
    Binding("P", "Place point", "Drop a point on the ground plane, or on the surface under the cursor",
            "place_point"),
    Binding("G", "Move", "Move the selection; X/Y/Z for an axis, Shift+X/Y/Z for a plane, "
                         "digits for an exact offset, Ctrl to snap to a surface, Esc to cancel", "move"),
    Binding("B", "Make block", "Build a block from 8 selected points (or 4, for a sketch quad), "
                               "in the order they were clicked", "make_block"),
    Binding("Delete", "Delete", "Delete the selected points, and the blocks and patch faces that use them",
            "delete"),
    Binding("Ctrl+S", "Save", "Write the .shape file", "save"),
]

# Key names above -> the imgui key the frame is tested against. Only plain keys appear
# here; chords and Delete are handled by `pressed` below.
_KEYS = {"P": psim.ImGuiKey_P, "G": psim.ImGuiKey_G, "B": psim.ImGuiKey_B,
         "Delete": psim.ImGuiKey_Delete}


def pressed(binding: Binding) -> bool:
    """True on the frame `binding`'s key goes down. A `Ctrl+`-prefixed key also requires
    the modifier; a plain key requires it to be *absent*, so Ctrl+S never also fires S."""
    chord, _, key = binding.key.rpartition("+")
    wants_ctrl = chord == "Ctrl"
    if psim.GetIO().KeyCtrl != wants_ctrl:
        return False
    return psim.IsKeyPressed(_KEYS.get(key, getattr(psim, f"ImGuiKey_{key}", None)), False)


def draw_help() -> None:
    """The 'available tools' window, straight from the table -- nothing on screen says what
    the keys are otherwise."""
    psim.SetNextWindowSize((330, 260), psim.ImGuiCond_FirstUseEver)
    if psim.Begin("Tools"):
        for binding in BINDINGS:
            psim.TextColored((0.75, 0.9, 1.0, 1.0), f"{binding.key:>7}  {binding.label}")
            psim.TextWrapped(f"         {binding.description}")
    psim.End()
