import numpy as np
import pytest

from classy_foundry.document import Cell, Document, Point


def cube_points(document: Document) -> list:
    """The 8 corners of a unit cube, in blockMesh vertex order."""
    bottom = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    return [document.add_point(p) for p in bottom] + [document.add_point([x, y, 1]) for x, y, _ in bottom]


def test_add_point_returns_a_distinct_object_each_time():
    document = Document()
    first = document.add_point([0, 0, 0])
    second = document.add_point([0, 0, 0])

    assert first is not second
    assert first != second                      # eq=False: equality is identity
    assert document.points == [first, second]
    assert isinstance(first, Point)
    assert isinstance(first.position, np.ndarray)


def test_add_cell_stores_points_in_given_order():
    document = Document()
    points = cube_points(document)
    cell = document.add_cell(points)

    assert cell.points == points                # same objects, same order
    assert document.cells == [cell]


def test_add_cell_accepts_four_points_for_the_sketch_case():
    document = Document()
    quad = [document.add_point([x, y, 0]) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]

    assert len(document.add_cell(quad).points) == 4


def test_add_cell_rejects_any_other_count():
    document = Document()
    points = [document.add_point([0, 0, 0]) for _ in range(5)]

    with pytest.raises(ValueError):
        document.add_cell(points)


def test_deleting_a_point_takes_its_cells_with_it():
    document = Document()
    points = cube_points(document)
    document.add_cell(points)

    document.delete_points([points[0]])

    assert document.cells == []
    assert points[0] not in document.points
    assert len(document.points) == 7             # the other seven survive


def test_deleting_a_cell_leaves_its_points_alone():
    document = Document()
    points = cube_points(document)
    cell = document.add_cell(points)

    document.delete_cells([cell])

    assert document.cells == []
    assert document.points == points


def test_deleting_a_point_drops_the_patch_faces_that_use_it():
    document = Document()
    points = cube_points(document)
    patch = document.add_patch("blade", surface="/tmp/blade.stl")
    document.assign_face(patch, points[:4])
    document.assign_face(patch, points[4:])

    document.delete_points([points[0]])

    assert patch.faces == [tuple(points[4:])]   # the top face is untouched
    assert patch in document.patches            # the patch itself survives, possibly faceless


def test_assign_face_demands_exactly_four_points():
    document = Document()
    points = cube_points(document)
    patch = document.add_patch("inlet")

    with pytest.raises(ValueError):
        document.assign_face(patch, points[:3])


def test_a_surfaced_patch_with_no_faces_is_a_backdrop():
    document = Document()
    patch = document.add_patch("hub", surface="/tmp/hub.stl")

    assert patch.faces == []
    assert patch.surface == "/tmp/hub.stl"


def test_indices_appear_nowhere_in_the_document_api():
    document = Document()
    points = cube_points(document)
    cell = document.add_cell(points)
    document.add_point([5, 5, 5])               # would renumber everything, index-based

    assert cell.points == points                # nothing to update: there are no numbers
    assert isinstance(cell, Cell)


def test_a_surface_patch_is_named_after_the_file():
    document = Document()

    patch = document.surface_patch("/models/blade.stl")

    assert patch.name == "blade"
    assert patch.surface == "/models/blade.stl"
    assert patch.faces == []                     # a backdrop until faces are assigned
    assert document.patches == [patch]


def test_loading_the_same_surface_twice_updates_one_patch():
    document = Document()
    first = document.surface_patch("/models/blade.stl")

    second = document.surface_patch("/elsewhere/blade.stl")

    assert second is first
    assert first.surface == "/elsewhere/blade.stl"
    assert len(document.patches) == 1


def test_a_surface_can_be_dropped_onto_a_patch_that_already_has_faces():
    """Load the STL after building: the patch keeps its faces and gains the surface."""
    document = Document()
    points = cube_points(document)
    patch = document.add_patch("blade")
    document.assign_face(patch, points[:4])

    document.surface_patch("/models/blade.stl")

    assert patch.surface == "/models/blade.stl"
    assert len(patch.faces) == 1


def test_extent_measures_the_model_so_speeds_can_scale_with_it():
    document = Document()
    document.add_point([0, 0, 0])
    document.add_point([4, 1, 1])

    assert np.isclose(document.extent, 4.0)


def test_an_empty_or_tiny_document_still_has_a_usable_extent():
    """Navigation and the gizmo divide by this, and a fresh document has no points."""
    assert np.isclose(Document().extent, 1.0)
