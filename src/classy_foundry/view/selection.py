"""Mirror Polyscope's viewport selection into the step list (viewport -> list).

Polyscope selects a structure on click; we read it each frame and make the matching
step active. Synced only on *change*, so selecting a step in the list isn't overwritten
by the stale viewport selection. Structure names equal step names; sketch substructures
are suffixed (`name::points`), stripped here.

`last_selection` is the structure we last reacted to — the dedup that stops a held
selection from re-firing. A *pick* pre-seeds it with the structure it just consumed
(`picker`), so the mirror won't move the editor onto the picked step. Polyscope commits
its own click-selection a frame or two later (on mouse release), so an *empty* selection
is treated as a transient and leaves both `active` and that prediction untouched — it
must not wipe the pre-seed before the real selection lands.
"""

import polyscope as ps


def apply_selection(model, session, name):
    """Set the active step from a selected structure `name` (empty = nothing selected).

    Returns True if the active step changed. Pure (no polyscope) for testability.
    """
    if not name:
        return False  # transient/empty: never changes active, and must not clear the
        #               last_selection prediction a pending pick may have pre-seeded
    if name == session.get("last_selection"):
        return False
    session["last_selection"] = name
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
