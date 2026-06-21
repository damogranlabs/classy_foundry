"""Schema kind -> ImGui widget registry, for the *scalar* field kinds.

Point inputs (`point` / `point_list`) and references (`ref`) need the model (candidate
ancestors) and the session (viewport-pick arming), so they are rendered in the panel,
not here.
"""

import polyscope.imgui as psim

# kind -> callable(value) -> (changed, new_value). Labels are hidden ("##v"); the panel
# draws the visible label and sets the item width, so widgets fill the available space.
WIDGETS = {
    "point3": lambda value: psim.InputFloat3("##v", value),
    "float": lambda value: psim.InputFloat("##v", value),
    "int": lambda value: psim.InputInt("##v", value),
}


def edit_field(spec, value):
    """Render one scalar schema field; return (changed, new_value), tuples -> lists."""
    changed, new = WIDGETS[spec["kind"]](value)
    return changed, list(new) if isinstance(new, tuple) else new
