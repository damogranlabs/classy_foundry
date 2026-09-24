import numpy as np

from classy_foundry.document import Document
from classy_foundry.geom import Axis, Plane
from classy_foundry.view.editor import Editor

VIEW_NORMAL = np.array([0.0, -1.0, 0.0])
X_AXIS = Axis(np.zeros(3), np.array([1.0, 0.0, 0.0]))


def eight_points(editor: Editor) -> list:
    bottom = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    return [editor.place_point(p) for p in bottom] + [editor.place_point([x, y, 1]) for x, y, _ in bottom]


def select_in_order(editor: Editor, points: list) -> None:
    """How the mouse does it: the first click replaces the selection, Shift-clicks add."""
    for index, point in enumerate(points):
        editor.select(point, additive=index > 0)


def test_a_placed_point_is_selected_so_it_can_be_moved_immediately():
    """`P` then `G` is how a point gets off the ground plane, so placing selects."""
    editor = Editor(Document())

    point = editor.place_point([0.0, 0.0, 0.0])

    assert editor.selection == [point]


def test_selection_preserves_click_order():
    editor = Editor(Document())
    points = eight_points(editor)

    select_in_order(editor, list(reversed(points)))

    assert editor.selection == list(reversed(points))


def test_a_non_additive_select_replaces_the_selection():
    editor = Editor(Document())
    points = eight_points(editor)
    editor.select(points[0], additive=True)

    editor.select(points[1], additive=False)

    assert editor.selection == [points[1]]


def test_toggling_a_point_off_and_on_never_duplicates_it():
    """Shift-clicking is a toggle, so a point can leave and come back -- but only once."""
    editor = Editor(Document())
    points = eight_points(editor)
    editor.select(points[0], additive=False)

    editor.select(points[0], additive=True)
    assert editor.selection == []

    editor.select(points[0], additive=True)
    assert editor.selection == [points[0]]


def test_make_block_consumes_eight_selected_points_in_order():
    editor = Editor(Document())
    points = eight_points(editor)
    select_in_order(editor, points)

    cell = editor.make_block()

    assert cell.points == points
    assert editor.document.cells == [cell]
    assert editor.selection == []          # consumed, ready for the next block


def test_make_block_with_a_wrong_count_does_nothing():
    editor = Editor(Document())
    points = eight_points(editor)
    select_in_order(editor, points[:5])

    assert editor.make_block() is None
    assert editor.document.cells == []
    assert len(editor.selection) == 5      # nothing consumed, nothing lost


def test_delete_removes_selected_points_and_clears_the_selection():
    editor = Editor(Document())
    points = eight_points(editor)
    editor.select(points[0], additive=False)

    editor.delete()

    assert points[0] not in editor.document.points
    assert editor.selection == []


def test_begin_move_defaults_to_the_selection_in_the_view_plane():
    editor = Editor(Document())
    points = eight_points(editor)
    editor.select(points[0], additive=False)

    editor.begin_move(view_normal=VIEW_NORMAL)

    assert editor.move is not None
    assert editor.move.points == [points[0]]
    assert isinstance(editor.move.constraint, Plane)
    assert np.allclose(editor.move.constraint.normal, VIEW_NORMAL)


def test_begin_move_with_no_selection_starts_nothing():
    editor = Editor(Document())

    editor.begin_move(view_normal=VIEW_NORMAL)

    assert editor.move is None


def test_begin_move_can_be_handed_explicit_points_and_a_constraint():
    """This is what a future extrude needs: move points it just made, along a normal."""
    editor = Editor(Document())
    points = eight_points(editor)

    editor.begin_move(points=points[4:], constraint=X_AXIS, view_normal=VIEW_NORMAL)

    assert editor.move.points == points[4:]
    assert editor.move.constraint is X_AXIS


def test_solve_uses_the_constraint_when_not_snapping():
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=False)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)

    solved = editor.solve(np.array([4.0, 3.0, 7.0]), np.array([0.0, 0.0, -1.0]))

    assert np.allclose(solved, [4.0, 0.0, 0.0])


def a_surfaced_editor(tmp_path) -> Editor:
    """An editor with a 2x2x2 box loaded as a reference surface, centred on the origin."""
    import trimesh

    stl = str(tmp_path / "box.stl")
    trimesh.creation.box(extents=(2.0, 2.0, 2.0)).export(stl)
    editor = Editor(Document())
    editor.document.surface_patch(stl)
    return editor


def test_snapping_on_an_axis_lands_on_the_axis(tmp_path):
    editor = a_surfaced_editor(tmp_path)
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=False)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)

    solved = editor.solve(np.array([5.0, 0.3, 0.4]), np.array([-1.0, 0.0, 0.0]), snapping=True)

    assert np.allclose(solved[[1, 2]], 0.0)         # pulled back onto the axis
    assert np.isclose(solved[0], 1.0)               # from the box's face


def test_snapping_with_the_cursor_off_the_surface_still_follows_the_mouse(tmp_path):
    """A miss must not freeze the point: it falls back to the plain ray solution."""
    editor = a_surfaced_editor(tmp_path)
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=False)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)

    solved = editor.solve(np.array([4.0, 9.0, 9.0]), np.array([0.0, 0.0, -1.0]), snapping=True)

    assert np.allclose(solved, [4.0, 0.0, 0.0])


def test_the_dragged_point_can_never_block_its_own_snapping(tmp_path):
    """The point being moved sits under the cursor; snapping intersects the mesh itself,
    so the point is not in the way and cannot make the target jump."""
    editor = a_surfaced_editor(tmp_path)
    point = editor.place_point([1.0, 0.3, 0.4])     # sitting right on the surface
    editor.select(point, additive=False)
    editor.begin_move(view_normal=np.array([-1.0, 0.0, 0.0]))

    solved = editor.solve(np.array([5.0, 0.3, 0.4]), np.array([-1.0, 0.0, 0.0]), snapping=True)

    assert np.allclose(solved, [1.0, 0.3, 0.4])


def test_surfaces_lists_only_files_that_are_there(tmp_path):
    editor = a_surfaced_editor(tmp_path)
    editor.document.surface_patch("/nowhere/gone.stl")

    assert len(editor.surfaces()) == 1


def test_cancel_move_restores_positions_and_ends_the_modal():
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=False)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)
    editor.move.to(np.array([0.0, 0.0, 0.0]))
    editor.move.to(np.array([5.0, 0.0, 0.0]))

    editor.cancel_move()

    assert np.allclose(point.position, [0.0, 0.0, 0.0])
    assert editor.move is None


def test_confirm_move_keeps_positions_and_ends_the_modal():
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=False)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)
    editor.move.to(np.array([0.0, 0.0, 0.0]))
    editor.move.to(np.array([5.0, 0.0, 0.0]))

    editor.confirm_move()

    assert np.allclose(point.position, [5.0, 0.0, 0.0])
    assert editor.move is None


def test_constrain_to_axis_switches_the_live_move():
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=False)
    editor.begin_move(view_normal=VIEW_NORMAL)

    editor.constrain("Y")

    assert isinstance(editor.move.constraint, Axis)
    assert np.allclose(editor.move.constraint.direction, [0.0, 1.0, 0.0])


def test_constrain_to_plane_uses_the_perpendicular_convention():
    """Blender: Shift+Z means 'everything except Z' -- the XY plane."""
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=False)
    editor.begin_move(view_normal=VIEW_NORMAL)

    editor.constrain("Z", perpendicular=True)

    assert isinstance(editor.move.constraint, Plane)
    assert np.allclose(editor.move.constraint.normal, [0.0, 0.0, 1.0])


def test_dispatch_runs_the_named_action():
    editor = Editor(Document())
    points = eight_points(editor)
    select_in_order(editor, points)

    assert editor.dispatch("make_block", view_normal=VIEW_NORMAL) is True
    assert len(editor.document.cells) == 1


# ---------- duplicate: the cheap way to place a point near another ----------

def test_duplicate_copies_the_selection_and_grabs_the_copies():
    editor = Editor(Document())
    points = eight_points(editor)
    select_in_order(editor, points[:4])

    editor.duplicate(view_normal=VIEW_NORMAL)

    assert len(editor.document.points) == 12
    assert editor.selection == editor.document.points[8:]     # the copies, in the same order
    assert editor.move is not None
    assert editor.move.points == editor.selection             # already grabbed


def test_a_copy_starts_where_its_original_is_but_is_its_own_point():
    editor = Editor(Document())
    original = editor.place_point([1.0, 2.0, 3.0])
    editor.select(original, additive=False)

    editor.duplicate(view_normal=VIEW_NORMAL)
    copy = editor.selection[0]

    assert copy is not original
    assert np.allclose(copy.position, original.position)

    editor.move.to(np.array([0.0, 0.0, 0.0]))
    editor.move.to(np.array([5.0, 0.0, 0.0]))

    assert np.allclose(original.position, [1.0, 2.0, 3.0])    # the original stays put


def test_cancelling_a_duplicate_discards_the_copies_instead_of_stacking_them():
    """Esc after C must leave nothing behind -- coincident points are exactly what this
    feature exists to avoid."""
    editor = Editor(Document())
    points = eight_points(editor)
    select_in_order(editor, points[:4])
    editor.duplicate(view_normal=VIEW_NORMAL)

    editor.cancel_move()

    assert editor.document.points == points
    assert editor.selection == []
    assert editor.move is None


def test_confirming_a_duplicate_keeps_the_copies():
    editor = Editor(Document())
    original = editor.place_point([0.0, 0.0, 0.0])
    editor.select(original, additive=False)
    editor.duplicate(view_normal=VIEW_NORMAL)
    editor.move.to(np.array([0.0, 0.0, 0.0]))
    editor.move.to(np.array([2.0, 0.0, 0.0]))

    editor.confirm_move()

    assert len(editor.document.points) == 2
    assert np.allclose(editor.document.points[1].position, [2.0, 0.0, 0.0])


def test_cancelling_an_ordinary_move_deletes_nothing():
    editor = Editor(Document())
    points = eight_points(editor)
    editor.select(points[0], additive=False)
    editor.begin_move(view_normal=VIEW_NORMAL)

    editor.cancel_move()

    assert editor.document.points == points


def test_duplicating_nothing_does_nothing():
    editor = Editor(Document())

    editor.duplicate(view_normal=VIEW_NORMAL)

    assert editor.document.points == []
    assert editor.move is None


def test_a_duplicated_face_can_be_moved_along_an_axis_and_blocked():
    """The workflow this is for: copy a quad, push it, and the eight points make a hex."""
    editor = Editor(Document())
    quad = [editor.place_point([x, y, 0.0]) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
    select_in_order(editor, quad)

    editor.duplicate(view_normal=VIEW_NORMAL)
    editor.constrain("Z")
    editor.move.by(1.0)
    editor.confirm_move()
    select_in_order(editor, quad + editor.document.points[4:])

    cell = editor.make_block()

    assert len(cell.points) == 8
    assert np.allclose(cell.points[4].position, [0.0, 0.0, 1.0])


# ---------- blocks: selecting and deleting them ----------

def a_block(editor: Editor):
    points = eight_points(editor)
    select_in_order(editor, points)
    return editor.make_block(), points


def test_selecting_a_block_does_not_disturb_the_point_selection_rules():
    editor = Editor(Document())
    cell, _ = a_block(editor)

    editor.select_cell(cell, additive=False)

    assert editor.cells == [cell]
    assert editor.selection == []


def test_shift_click_adds_a_second_block():
    editor = Editor(Document())
    first, _ = a_block(editor)
    second, _ = a_block(editor)

    editor.select_cell(first, additive=False)
    editor.select_cell(second, additive=True)

    assert editor.cells == [first, second]


def test_a_plain_click_on_a_point_clears_the_block_selection():
    editor = Editor(Document())
    cell, points = a_block(editor)
    editor.select_cell(cell, additive=False)

    editor.select(points[0], additive=False)

    assert editor.cells == []
    assert editor.selection == [points[0]]


def test_deleting_a_selected_block_keeps_its_points():
    """Blocks are topology: removing one should not remove the geometry it was built on."""
    editor = Editor(Document())
    cell, points = a_block(editor)
    editor.select_cell(cell, additive=False)

    editor.delete()

    assert editor.document.cells == []
    assert editor.document.points == points
    assert editor.cells == []


def test_deleting_points_and_blocks_together_does_both():
    editor = Editor(Document())
    first, points = a_block(editor)
    second, more = a_block(editor)
    editor.select_cell(second, additive=False)
    editor.select(points[0], additive=True)       # Shift-click a point of the *first* block

    editor.delete()

    assert editor.document.cells == []            # second deleted outright, first cascaded
    assert points[0] not in editor.document.points
    assert more == [point for point in more if point in editor.document.points]


def test_clearing_the_selection_clears_both_kinds():
    editor = Editor(Document())
    cell, points = a_block(editor)
    editor.select_cell(cell, additive=False)
    editor.select(points[0], additive=True)

    editor.clear_selection()

    assert editor.selection == []
    assert editor.cells == []


# ---------- deselecting ----------

def test_shift_clicking_a_selected_point_again_removes_it():
    editor = Editor(Document())
    points = eight_points(editor)
    select_in_order(editor, points[:3])

    editor.select(points[1], additive=True)

    assert editor.selection == [points[0], points[2]]   # the rest keep their order


def test_shift_clicking_a_selected_block_again_removes_it():
    editor = Editor(Document())
    first, _ = a_block(editor)
    second, _ = a_block(editor)
    editor.select_cell(first, additive=False)
    editor.select_cell(second, additive=True)

    editor.select_cell(first, additive=True)

    assert editor.cells == [second]


def test_a_plain_click_on_a_selected_point_keeps_just_that_one():
    """Without Shift it is a fresh selection, not a toggle -- otherwise clicking the point
    you mean would empty the selection."""
    editor = Editor(Document())
    points = eight_points(editor)
    select_in_order(editor, points[:3])

    editor.select(points[1], additive=False)

    assert editor.selection == [points[1]]


def test_clicking_nothing_clears_the_selection():
    editor = Editor(Document())
    cell, points = a_block(editor)
    editor.select_cell(cell, additive=False)
    editor.select(points[0], additive=True)

    editor.select_nothing(additive=False)

    assert editor.selection == []
    assert editor.cells == []


def test_shift_clicking_nothing_keeps_the_selection():
    """A missed Shift-click is a slip of the hand, not an instruction to start over."""
    editor = Editor(Document())
    cell, _ = a_block(editor)
    editor.select_cell(cell, additive=False)

    editor.select_nothing(additive=True)

    assert editor.cells == [cell]
