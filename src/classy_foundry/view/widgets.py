"""Schema kind -> ImGui widget registry, for the *scalar* field kinds.

Point inputs (`point` / `point_list`) and references (`ref`) need the model (candidate
ancestors) and the session (viewport-pick arming), so they are rendered in the panel,
not here.
"""

import polyscope.imgui as psim

# kind -> callable(spec, value) -> (changed, new_value). Labels are hidden ("##v"); the
# panel draws the visible label and sets the item width, so widgets fill the available
# space. `float`/`int` are *expression strings* (e.g. "pi/2"), so they edit as free text and
# are evaluated at build time (see steps.base.eval_expr); str() coerces legacy numeric
# values. `choice` reads its options from the field's `choices` (hence the spec arg).
WIDGETS = {
    "point3": lambda spec, value: psim.InputFloat3("##v", value),
    "float": lambda spec, value: psim.InputText("##v", str(value)),
    "int": lambda spec, value: psim.InputText("##v", str(value)),
    "points_file": lambda spec, value: psim.InputText("##v", str(value)),  # path to a points file
    "choice": lambda spec, value: _combo(spec, value),
}


def _combo(spec, value):
    """A dropdown over the field's `choices`; Polyscope's Combo works on the index."""
    choices = spec["choices"]
    index = choices.index(value) if value in choices else 0
    changed, new_index = psim.Combo("##v", index, choices)
    return changed, choices[new_index]


def edit_field(spec, value):
    """Render one scalar schema field; return (changed, new_value), tuples -> lists."""
    changed, new = WIDGETS[spec["kind"]](spec, value)
    return changed, list(new) if isinstance(new, tuple) else new
