"""Mirror Polyscope's viewport selection into the step list (viewport -> list).

Polyscope selects a structure on click; we read it each frame and make the matching
step active. Synced only on *change*, so selecting a step in the list isn't overwritten
by the stale viewport selection. Structure names equal step names; sketch substructures
are suffixed (`name::points`), stripped here.
"""

import polyscope as ps


def apply_selection(model, session, name):
    """Set the active step from a selected structure `name` (None = nothing selected).

    Returns True if the active step changed. Pure (no polyscope) for testability.
    """
    if name == session.get("last_selection"):
        return False
    session["last_selection"] = name
    if not name:
        return False
    step = model.step_by_name(name.split("::")[0])
    if step is None or step is session.get("active"):
        return False
    session["active"] = step
    return True


def sync_selection(model, session):
    """Read Polyscope's current viewport selection and apply it to the step list."""
    if not ps.have_selection():
        return apply_selection(model, session, None)
    try:
        name = ps.get_selection().structure_name
    except RuntimeError:
        ps.reset_selection()  # selection went stale (structures rebuilt); drop it
        return apply_selection(model, session, None)
    return apply_selection(model, session, name)
