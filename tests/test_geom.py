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


# ---------- snapping to a loaded surface ----------

def a_box():
    """A 2x2x2 box centred on the origin, as a loaded reference surface would be."""
    import trimesh

    return trimesh.creation.box(extents=(2.0, 2.0, 2.0))


def test_surface_hit_finds_where_the_ray_meets_the_mesh():
    from classy_foundry.geom import surface_hit

    hit = surface_hit(np.array([5.0, 0.2, 0.3]), np.array([-1.0, 0.0, 0.0]), [a_box()])

    assert np.allclose(hit, [1.0, 0.2, 0.3])


def test_surface_hit_takes_the_nearest_of_several_surfaces():
    import trimesh

    from classy_foundry.geom import surface_hit

    near = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    far = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    far.apply_translation([-10.0, 0.0, 0.0])

    hit = surface_hit(np.array([5.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]), [near, far])

    assert np.allclose(hit, [1.0, 0.0, 0.0])


def test_surface_hit_is_none_when_the_ray_misses():
    from classy_foundry.geom import surface_hit

    assert surface_hit(np.array([5.0, 5.0, 5.0]), np.array([0.0, 0.0, 1.0]), [a_box()]) is None


def test_surface_hit_is_none_without_any_surfaces():
    from classy_foundry.geom import surface_hit

    assert surface_hit(np.zeros(3), np.array([1.0, 0.0, 0.0]), []) is None


def test_free_move_snapping_sticks_to_the_surface_under_the_cursor():
    """A free move follows the surface itself -- that is what makes it feel attached."""
    from classy_foundry.geom import FreePlane

    free = FreePlane(np.zeros(3), np.array([0.0, -1.0, 0.0]))    # camera-facing

    snapped = free.snap(np.array([5.0, 0.2, 0.3]), np.array([-1.0, 0.0, 0.0]), [a_box()])

    assert np.allclose(snapped, [1.0, 0.2, 0.3])


def test_plane_snapping_traces_the_cross_section_not_the_projection():
    """The point must land where the plane cuts the surface, so a drag traces that
    section. A projection would sit on the plane but *off* the surface."""
    plane = Plane(np.zeros(3), Z)                                # the XY plane, z = 0

    snapped = plane.snap(np.array([5.0, 0.2, 3.0]), np.array([-1.0, 0.0, -0.6]), [a_box()])

    assert np.isclose(snapped[2], 0.0)                           # on the plane
    assert np.isclose(abs(snapped[0]), 1.0, atol=1e-6)           # and on the box's side


def test_plane_snapping_follows_the_cursor_along_the_section():
    """Two nearby rays give two nearby points on the section -- no jumping."""
    plane = Plane(np.zeros(3), Z)

    first = plane.snap(np.array([5.0, 0.20, 0.0]), np.array([-1.0, 0.0, 0.0]), [a_box()])
    second = plane.snap(np.array([5.0, 0.25, 0.0]), np.array([-1.0, 0.0, 0.0]), [a_box()])

    assert np.allclose(first, [1.0, 0.20, 0.0], atol=1e-6)
    assert np.allclose(second, [1.0, 0.25, 0.0], atol=1e-6)


def test_plane_snapping_is_none_when_the_plane_misses_the_surface():
    plane = Plane(np.array([0.0, 0.0, 50.0]), Z)                 # well above the box

    assert plane.snap(np.array([5.0, 0.0, 50.0]), np.array([-1.0, 0.0, 0.0]), [a_box()]) is None


def test_axis_snapping_keeps_the_point_on_the_axis():
    axis = Axis(np.zeros(3), X)

    snapped = axis.snap(np.array([5.0, 0.4, 3.0]), np.array([-1.0, 0.0, -0.6]), [a_box()])

    assert np.allclose(snapped[[1, 2]], 0.0)                     # on the axis
    assert snapped[0] != 0.0


def test_snapping_without_surfaces_gives_nothing_to_snap_to():
    for constraint in (Plane(np.zeros(3), Z), Axis(np.zeros(3), X)):
        assert constraint.snap(np.array([5.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]), []) is None
