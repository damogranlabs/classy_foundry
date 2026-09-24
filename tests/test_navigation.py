"""Turntable navigation: what a puck deflection does to the camera. Pure math.

The two modes are the classic 3Dconnexion split: in **object** mode the puck moves the
model (so the camera does the opposite, and orbits around the model); in **camera** mode
the puck moves the eye.
"""

import numpy as np

from classy_foundry.navigation import (
    CAMERA,
    FULL_DEFLECTION,
    OBJECT,
    Sensitivity,
    View,
    navigate,
)
from classy_foundry.spacemouse import Motion

EXTENT = 2.0
DT = 0.1
Z_UP = np.array([0.0, 0.0, 1.0])

# These tests describe what each *mode* means, so they pin their own sensitivities: the
# ones in `navigation` are a user preference (any of them may be negative) and must never
# decide whether the suite passes.
PLAIN = Sensitivity(pan=0.7, dolly=1.2, orbit=1.5)


def a_view() -> View:
    """Looking at the origin from 10 along -Y, Z up -- forward is +Y."""
    return View(position=np.array([0.0, -10.0, 0.0]), target=np.zeros(3), up=Z_UP)


def push(translation=(0, 0, 0), rotation=(0, 0, 0)) -> Motion:
    """A deflection given as a fraction of full scale, the way a hand gives it."""
    return Motion(np.asarray(translation, dtype=float) * FULL_DEFLECTION,
                  np.asarray(rotation, dtype=float) * FULL_DEFLECTION)


def distance(view: View) -> float:
    return float(np.linalg.norm(view.position - view.target))


# ---------- shared by both modes ----------

def test_a_still_puck_leaves_the_camera_alone():
    for mode in (OBJECT, CAMERA):
        view = a_view()

        moved = navigate(view, push(), EXTENT, DT, PLAIN, mode)

        assert np.allclose(moved.position, view.position)
        assert np.allclose(moved.target, view.target)


def test_panning_slides_camera_and_target_together_in_both_modes():
    for mode in (OBJECT, CAMERA):
        view = a_view()

        moved = navigate(view, push(translation=(1, 0, 0)), EXTENT, DT, PLAIN, mode)

        shift = moved.position - view.position
        assert np.allclose(moved.target - view.target, shift)
        assert shift[0] != 0 and np.allclose(shift[[1, 2]], 0)
        assert np.isclose(distance(moved), distance(view))


def test_the_up_direction_is_preserved_so_the_horizon_never_rolls():
    for mode in (OBJECT, CAMERA):
        moved = navigate(a_view(), push(rotation=(1, 1, 1)), EXTENT, DT, PLAIN, mode)

        assert np.allclose(moved.up, Z_UP)


def test_a_bigger_model_pans_proportionally_faster():
    small = navigate(a_view(), push(translation=(1, 0, 0)), 1.0, DT, PLAIN)
    large = navigate(a_view(), push(translation=(1, 0, 0)), 10.0, DT, PLAIN)

    assert np.linalg.norm(large.position - a_view().position) > \
           np.linalg.norm(small.position - a_view().position)


# ---------- object mode: the puck moves the model ----------

def test_object_mode_pushing_right_sends_the_model_right_so_the_camera_goes_left():
    view = a_view()                                    # forward is +Y, so camera right is +X

    moved = navigate(view, push(translation=(1, 0, 0)), EXTENT, DT, PLAIN, OBJECT)

    assert moved.position[0] < view.position[0]


def test_object_mode_pulling_the_puck_toward_you_brings_the_model_closer():
    view = a_view()

    moved = navigate(view, push(translation=(0, 0, 1)), EXTENT, DT, PLAIN, OBJECT)

    assert distance(moved) < distance(view)
    assert np.allclose(moved.target, view.target)


def test_object_mode_orbits_the_model_keeping_it_in_the_middle():
    view = a_view()

    moved = navigate(view, push(rotation=(0, 1, 0)), EXTENT, DT, PLAIN, OBJECT)

    assert np.allclose(moved.target, view.target)      # the model stays put; the eye goes round
    assert np.isclose(distance(moved), distance(view))
    assert not np.allclose(moved.position, view.position)
    assert np.isclose(moved.position[2], view.position[2])


def test_object_mode_tilting_changes_elevation_at_constant_distance():
    view = a_view()

    moved = navigate(view, push(rotation=(1, 0, 0)), EXTENT, DT, PLAIN, OBJECT)

    assert np.isclose(distance(moved), distance(view))
    assert not np.isclose(moved.position[2], view.position[2])


def test_object_mode_never_zooms_through_the_model():
    view = a_view()

    for _ in range(200):
        view = navigate(view, push(translation=(0, 0, 1)), EXTENT, DT, PLAIN, OBJECT)

    assert distance(view) > 0


def test_object_mode_tilting_forever_stops_at_the_pole():
    view = a_view()

    for _ in range(500):
        view = navigate(view, push(rotation=(1, 0, 0)), EXTENT, DT, PLAIN, OBJECT)

    direction = (view.position - view.target) / distance(view)
    assert abs(direction[2]) < 1.0
    assert np.isclose(distance(view), 10.0)


# ---------- camera mode: the puck moves the eye ----------

def test_camera_mode_pushing_right_moves_the_camera_right():
    view = a_view()

    moved = navigate(view, push(translation=(1, 0, 0)), EXTENT, DT, PLAIN, CAMERA)

    assert moved.position[0] > view.position[0]


def test_camera_mode_pushing_forward_flies_through_the_scene():
    """No clamp: the eye travels, target and all, instead of zooming onto a model."""
    view = a_view()

    moved = navigate(view, push(translation=(0, 0, -1)), EXTENT, DT, PLAIN, CAMERA)

    assert moved.position[1] > view.position[1]                     # advanced along +Y
    assert np.isclose(distance(moved), distance(view))              # the pivot came along


def test_camera_mode_flying_forever_passes_right_through_the_target():
    view = a_view()

    for _ in range(200):
        view = navigate(view, push(translation=(0, 0, -1)), EXTENT, DT, PLAIN, CAMERA)

    assert view.position[1] > 0                                     # out the other side


def test_camera_mode_looks_around_from_where_it_stands():
    view = a_view()

    moved = navigate(view, push(rotation=(0, 1, 0)), EXTENT, DT, PLAIN, CAMERA)

    assert np.allclose(moved.position, view.position)               # the eye stays put
    assert not np.allclose(moved.target, view.target)               # the gaze turns


# ---------- tuning ----------

def test_a_negative_sensitivity_inverts_that_axis_alone():
    forward = Sensitivity(pan=0.7)
    backward = Sensitivity(pan=-0.7)

    one = navigate(a_view(), push(translation=(1, 0, 0)), EXTENT, DT, forward)
    other = navigate(a_view(), push(translation=(1, 0, 0)), EXTENT, DT, backward)

    assert np.allclose(one.position - a_view().position, -(other.position - a_view().position))
