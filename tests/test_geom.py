import numpy as np

from classy_foundry.geom import Axis, Plane

DOWN = np.array([0.0, 0.0, -1.0])


def test_plane_from_ray_hits_where_the_ray_crosses_it():
    plane = Plane(np.array([0.0, 0.0, 2.0]), np.array([0.0, 0.0, 1.0]))

    hit = plane.from_ray(np.array([1.0, 1.0, 10.0]), DOWN)

    assert np.allclose(hit, [1.0, 1.0, 2.0])


def test_plane_from_ray_returns_none_when_parallel():
    plane = Plane(np.zeros(3), np.array([0.0, 0.0, 1.0]))

    assert plane.from_ray(np.array([0.0, 0.0, 5.0]), np.array([1.0, 0.0, 0.0])) is None


def test_plane_project_drops_the_off_plane_component():
    plane = Plane(np.array([0.0, 0.0, 3.0]), np.array([0.0, 0.0, 2.0]))   # unnormalised normal

    assert np.allclose(plane.project(np.array([1.0, 2.0, 9.0])), [1.0, 2.0, 3.0])


def test_plane_offset_is_zero_because_a_number_means_nothing_in_a_plane():
    plane = Plane(np.zeros(3), np.array([0.0, 0.0, 1.0]))

    assert np.allclose(plane.offset(5.0), np.zeros(3))


def test_axis_from_ray_returns_the_closest_point_on_the_axis():
    axis = Axis(np.zeros(3), np.array([1.0, 0.0, 0.0]))

    closest = axis.from_ray(np.array([4.0, 3.0, 7.0]), DOWN)   # a vertical ray through x=4

    assert np.allclose(closest, [4.0, 0.0, 0.0])


def test_axis_from_ray_returns_none_when_the_ray_is_parallel_to_the_axis():
    axis = Axis(np.zeros(3), np.array([1.0, 0.0, 0.0]))

    assert axis.from_ray(np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0])) is None


def test_axis_project_is_the_foot_of_the_perpendicular():
    axis = Axis(np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 4.0]))     # unnormalised

    assert np.allclose(axis.project(np.array([5.0, 6.0, 2.0])), [0.0, 1.0, 2.0])


def test_axis_offset_walks_along_the_direction():
    axis = Axis(np.zeros(3), np.array([0.0, 3.0, 0.0]))

    assert np.allclose(axis.offset(2.0), [0.0, 2.0, 0.0])


def test_a_snapped_point_stays_on_its_constraint():
    """Snapping while constrained: the surface hit is projected back, so the move stays
    on the axis."""
    axis = Axis(np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]))
    surface_hit = np.array([3.0, 2.5, -1.0])

    assert np.allclose(axis.project(surface_hit), [3.0, 0.0, 0.0])


X, Y, Z = np.eye(3)


def test_an_axis_constraint_allows_only_its_own_direction():
    axis = Axis(np.zeros(3), X)

    assert axis.allows(X)
    assert not axis.allows(Y)
    assert not axis.allows(Z)


def test_an_axis_constraint_allows_its_direction_reversed():
    axis = Axis(np.zeros(3), np.array([0.0, -5.0, 0.0]))

    assert axis.allows(Y)


def test_a_plane_constraint_allows_the_two_axes_lying_in_it():
    plane = Plane(np.zeros(3), Z)          # Shift+Z: the XY plane

    assert plane.allows(X)
    assert plane.allows(Y)
    assert not plane.allows(Z)


def test_a_camera_facing_plane_allows_no_world_axis():
    """A free move is not axis-aligned, so nothing lights up -- which is what it means."""
    plane = Plane(np.zeros(3), np.array([0.3, -0.5, 0.81]))

    assert not any(plane.allows(axis) for axis in (X, Y, Z))
