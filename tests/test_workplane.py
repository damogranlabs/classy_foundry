"""The work plane: polyscope's slice plane, read as a `geom.Plane`.

Its pose is the single source of truth -- dragging polyscope's widget, typing numbers and
following the camera all write to the same place, so nothing can get out of sync.
"""

import numpy as np
import polyscope as ps
import polyscope.imgui as psim
import pytest

from classy_foundry.document import Document
from classy_foundry.geom import Plane
from classy_foundry.view import scene
from classy_foundry.view.workplane import WorkPlane, draw_settings


@pytest.fixture(scope="module")
def mock_polyscope():
    ps.set_allow_headless_backends(True)
    ps.init("openGL_mock")
    ps.set_up_dir("z_up")
    yield
    ps.shutdown()


@pytest.fixture
def work_plane(mock_polyscope):
    plane = WorkPlane.attach()
    yield plane
    plane.remove()


def test_it_starts_on_the_ground_not_cutting_anything(work_plane):
    """A plane that started slicing would surprise anyone opening an existing model."""
    assert np.allclose(work_plane.plane.origin, 0.0)
    assert np.allclose(np.abs(work_plane.plane.normal), [0.0, 0.0, 1.0])
    assert work_plane.cutting is False
    assert work_plane.following is False


def test_nothing_is_cut_until_cutting_is_asked_for(mock_polyscope):
    """An inactive slice plane loses its pose, so the plane is always active and 'no
    cutting' means every structure is exempt."""
    plane = WorkPlane.attach()
    document = Document()
    cube = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    points = [document.add_point(p) for p in cube] + [document.add_point([x, y, 1]) for x, y, _ in cube]
    document.add_cell(points)
    structures = scene.sync(document)

    plane.apply(structures)
    assert all(structure.get_ignore_slice_plane(plane.name) for structure in structures.values())

    plane.cutting = True
    plane.apply(structures)
    assert structures[scene.CELLS_NAME].get_ignore_slice_plane(plane.name) is False
    assert structures[scene.POINTS_NAME].get_ignore_slice_plane(plane.name) is True  # never the points
    plane.remove()


def test_it_reads_back_as_a_geom_plane(work_plane):
    work_plane.set_pose([0.0, 0.0, 2.0], [0.0, 0.0, 1.0])

    plane = work_plane.plane

    assert isinstance(plane, Plane)
    assert np.allclose(plane.from_ray([1.0, 1.0, 9.0], [0.0, 0.0, -1.0]), [1.0, 1.0, 2.0])


def test_a_typed_normal_need_not_be_a_unit_vector(work_plane):
    work_plane.set_pose([0.0, 0.0, 1.0], [0.0, 0.0, 5.0])

    assert np.allclose(work_plane.plane.normal, [0.0, 0.0, 1.0])


def test_a_degenerate_normal_is_refused_rather_than_breaking_the_plane(work_plane):
    work_plane.set_pose([0.0, 0.0, 1.0], [0.0, 0.0, 1.0])

    work_plane.set_pose([0.0, 0.0, 1.0], [0.0, 0.0, 0.0])

    assert np.allclose(work_plane.plane.normal, [0.0, 0.0, 1.0])     # the last good one stands


def test_following_puts_it_across_the_view_at_the_pivot(work_plane):
    work_plane.following = True

    work_plane.follow(pivot=np.array([1.0, 2.0, 3.0]), look_dir=np.array([0.0, 1.0, 0.0]))

    assert np.allclose(work_plane.plane.origin, [1.0, 2.0, 3.0])
    assert np.allclose(np.abs(work_plane.plane.normal), [0.0, 1.0, 0.0])


def test_a_locked_plane_ignores_the_camera(work_plane):
    work_plane.set_pose([0.0, 0.0, 4.0], [0.0, 0.0, 1.0])
    work_plane.following = False

    work_plane.follow(pivot=np.array([9.0, 9.0, 9.0]), look_dir=np.array([0.0, 1.0, 0.0]))

    assert np.allclose(work_plane.plane.origin, [0.0, 0.0, 4.0])


def test_cutting_can_be_switched_on_and_off(work_plane):
    work_plane.cutting = True
    assert work_plane.cutting is True

    work_plane.cutting = False
    assert work_plane.cutting is False


def test_the_panel_draws_in_both_states(work_plane):
    ps.frame_tick()

    if psim.Begin("test"):
        draw_settings(work_plane)
        work_plane.following = True
        draw_settings(work_plane)
    psim.End()
