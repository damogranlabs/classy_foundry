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


def test_selecting_the_same_point_again_additively_does_not_duplicate_it():
    editor = Editor(Document())
    points = eight_points(editor)
    editor.select(points[0], additive=False)

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
    editor.select(point, additive=True)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)

    solved = editor.solve(np.array([4.0, 3.0, 7.0]), np.array([0.0, 0.0, -1.0]))

    assert np.allclose(solved, [4.0, 0.0, 0.0])


def test_solve_projects_a_surface_hit_back_onto_the_constraint():
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=True)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)

    solved = editor.solve(np.array([0.0, 0.0, 9.0]), np.array([0.0, 0.0, -1.0]),
                          surface_hit=np.array([3.0, 2.0, 1.0]))

    assert np.allclose(solved, [3.0, 0.0, 0.0])


def test_cancel_move_restores_positions_and_ends_the_modal():
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=True)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)
    editor.move.to(np.array([0.0, 0.0, 0.0]))
    editor.move.to(np.array([5.0, 0.0, 0.0]))

    editor.cancel_move()

    assert np.allclose(point.position, [0.0, 0.0, 0.0])
    assert editor.move is None


def test_confirm_move_keeps_positions_and_ends_the_modal():
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=True)
    editor.begin_move(constraint=X_AXIS, view_normal=VIEW_NORMAL)
    editor.move.to(np.array([0.0, 0.0, 0.0]))
    editor.move.to(np.array([5.0, 0.0, 0.0]))

    editor.confirm_move()

    assert np.allclose(point.position, [5.0, 0.0, 0.0])
    assert editor.move is None


def test_constrain_to_axis_switches_the_live_move():
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=True)
    editor.begin_move(view_normal=VIEW_NORMAL)

    editor.constrain("Y")

    assert isinstance(editor.move.constraint, Axis)
    assert np.allclose(editor.move.constraint.direction, [0.0, 1.0, 0.0])


def test_constrain_to_plane_uses_the_perpendicular_convention():
    """Blender: Shift+Z means 'everything except Z' -- the XY plane."""
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=True)
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
