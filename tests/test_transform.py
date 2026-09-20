import numpy as np

from classy_foundry.document import Document
from classy_foundry.geom import Axis, Plane
from classy_foundry.transform import Move

X_AXIS = Axis(np.zeros(3), np.array([1.0, 0.0, 0.0]))


def two_points() -> tuple:
    document = Document()
    return document, [document.add_point([0.0, 0.0, 0.0]), document.add_point([2.0, 0.0, 0.0])]


def test_the_first_to_call_only_sets_the_reference():
    _, points = two_points()
    move = Move.start(points, X_AXIS)

    move.to(np.array([10.0, 0.0, 0.0]))

    assert np.allclose(points[0].position, [0.0, 0.0, 0.0])
    assert np.allclose(points[1].position, [2.0, 0.0, 0.0])


def test_subsequent_moves_translate_by_the_delta_from_the_reference():
    _, points = two_points()
    move = Move.start(points, X_AXIS)
    move.to(np.array([10.0, 0.0, 0.0]))

    move.to(np.array([13.0, 0.0, 0.0]))

    assert np.allclose(points[0].position, [3.0, 0.0, 0.0])
    assert np.allclose(points[1].position, [5.0, 0.0, 0.0])


def test_moving_is_absolute_not_cumulative():
    _, points = two_points()
    move = Move.start(points, X_AXIS)
    move.to(np.array([0.0, 0.0, 0.0]))
    move.to(np.array([5.0, 0.0, 0.0]))

    move.to(np.array([1.0, 0.0, 0.0]))

    assert np.allclose(points[0].position, [1.0, 0.0, 0.0])


def test_cancel_restores_the_original_positions():
    _, points = two_points()
    move = Move.start(points, X_AXIS)
    move.to(np.array([0.0, 0.0, 0.0]))
    move.to(np.array([7.0, 3.0, 1.0]))

    move.cancel()

    assert np.allclose(points[0].position, [0.0, 0.0, 0.0])
    assert np.allclose(points[1].position, [2.0, 0.0, 0.0])


def test_confirm_keeps_the_new_positions_and_a_later_cancel_cannot_undo_them():
    _, points = two_points()
    move = Move.start(points, X_AXIS)
    move.to(np.array([0.0, 0.0, 0.0]))
    move.to(np.array([4.0, 0.0, 0.0]))

    move.confirm()
    move.cancel()

    assert np.allclose(points[0].position, [4.0, 0.0, 0.0])


def test_changing_the_constraint_restarts_from_the_originals():
    _, points = two_points()
    move = Move.start(points, Plane(np.zeros(3), np.array([0.0, 0.0, 1.0])))
    move.to(np.array([0.0, 0.0, 0.0]))
    move.to(np.array([6.0, 6.0, 0.0]))

    move.set_constraint(X_AXIS)

    assert np.allclose(points[0].position, [0.0, 0.0, 0.0])
    assert move.constraint is X_AXIS


def test_by_offsets_along_the_constraint_from_the_originals():
    _, points = two_points()
    move = Move.start(points, X_AXIS)

    move.by(1.5)

    assert np.allclose(points[0].position, [1.5, 0.0, 0.0])
    assert np.allclose(points[1].position, [3.5, 0.0, 0.0])


def test_by_in_a_plane_moves_nothing():
    _, points = two_points()
    move = Move.start(points, Plane(np.zeros(3), np.array([0.0, 0.0, 1.0])))

    move.by(9.0)

    assert np.allclose(points[0].position, [0.0, 0.0, 0.0])


def test_centroid_is_of_the_original_positions():
    _, points = two_points()
    move = Move.start(points, X_AXIS)
    move.to(np.array([0.0, 0.0, 0.0]))
    move.to(np.array([100.0, 0.0, 0.0]))

    assert np.allclose(move.centroid, [1.0, 0.0, 0.0])
