import numpy as np
import trimesh

from classy_foundry import storage
from classy_foundry.document import Document

CUBE = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]


def a_document(surface=None) -> Document:
    document = Document()
    points = [document.add_point(p) for p in CUBE]
    document.add_cell(points)
    patch = document.add_patch("top", surface=surface)
    document.assign_face(patch, points[4:])
    return document


def test_to_description_numbers_the_points_by_position():
    description = storage.to_description(a_document())

    assert np.allclose(description.points, CUBE)
    assert description.hexas == [list(range(8))]
    assert description.patches == {"top": [[4, 5, 6, 7]]}


def test_a_round_trip_through_a_file_reproduces_the_topology(tmp_path):
    path = str(tmp_path / "cube.shape")
    storage.save(a_document(), path)

    document = storage.load(path)

    assert len(document.points) == 8
    assert len(document.cells) == 1
    assert np.allclose([p.position for p in document.points], CUBE)


def test_loaded_cells_reference_the_documents_own_point_objects():
    """The whole point of the identity model: after loading, a cell's points *are* the
    document's points, so moving one moves the block."""
    document = storage.from_description(storage.to_description(a_document()))
    cell = document.cells[0]

    assert all(point in document.points for point in cell.points)
    assert cell.points[0] is document.points[0]


def test_loaded_patch_faces_reference_the_documents_own_points():
    document = storage.from_description(storage.to_description(a_document()))

    assert document.patches[0].faces[0][0] is document.points[4]


def test_a_shared_point_is_stored_once_and_stays_shared():
    document = Document()
    levels = [[document.add_point([x, y, z]) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))] for z in (0, 1, 2)]
    document.add_cell(levels[0] + levels[1])
    document.add_cell(levels[1] + levels[2])

    reloaded = storage.from_description(storage.to_description(document))

    assert len(reloaded.points) == 12                       # not 16: the middle four are shared
    assert reloaded.cells[0].points[4] is reloaded.cells[1].points[0]


def test_a_surface_survives_the_round_trip(tmp_path):
    stl = str(tmp_path / "top.stl")
    trimesh.creation.box().export(stl)
    path = str(tmp_path / "cube.shape")
    storage.save(a_document(surface=stl), path)

    document = storage.load(path)

    assert document.patches[0].surface == stl


def test_loading_a_missing_file_gives_an_empty_document(tmp_path):
    document = storage.load(str(tmp_path / "nothing-here.shape"))

    assert document.points == []
    assert document.cells == []
    assert document.patches == []
