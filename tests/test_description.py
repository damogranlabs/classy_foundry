import json

import numpy as np
import trimesh

from classy_foundry.description import FileSurface, MappedShapeDescription

CUBE = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]


def a_description(surfaces=None) -> MappedShapeDescription:
    return MappedShapeDescription(
        points=np.asarray(CUBE, dtype=float),
        hexas=[list(range(8))],
        patches={"top": [[4, 5, 6, 7]]},
        surfaces=surfaces or {},
    )


def write_stl(tmp_path, name="top.stl") -> str:
    path = tmp_path / name
    trimesh.creation.box().export(path)
    return str(path)


def test_save_writes_readable_json(tmp_path):
    path = tmp_path / "cube.shape"

    a_description().save(str(path))

    written = json.loads(path.read_text())
    assert written["points"][6] == [1.0, 1.0, 1.0]
    assert written["hexas"] == [list(range(8))]
    assert written["patches"] == {"top": [[4, 5, 6, 7]]}
    assert written["surfaces"] == {}


def test_each_point_and_block_is_one_line_so_diffs_read(tmp_path):
    path = tmp_path / "cube.shape"

    a_description().save(str(path))

    lines = [line.strip() for line in path.read_text().splitlines()]
    assert "[0.0, 0.0, 0.0]," in lines                      # a point, whole, on its own line
    assert "[0, 1, 2, 3, 4, 5, 6, 7]" in lines              # a block, likewise
    assert "[4, 5, 6, 7]" in lines                          # and a patch face
    assert json.loads(path.read_text())["hexas"] == [list(range(8))]   # still valid JSON


def test_a_round_trip_reproduces_the_topology(tmp_path):
    path = tmp_path / "cube.shape"
    a_description().save(str(path))

    loaded = MappedShapeDescription.load(str(path))

    assert np.allclose(loaded.points, CUBE)
    assert loaded.hexas == [list(range(8))]
    assert loaded.patches == {"top": [[4, 5, 6, 7]]}


def test_a_surface_is_written_as_a_path_relative_to_the_shape_file(tmp_path):
    stl = write_stl(tmp_path)
    path = tmp_path / "cube.shape"

    a_description({"top": FileSurface(stl)}).save(str(path))

    assert json.loads(path.read_text())["surfaces"] == {"top": "top.stl"}


def test_a_relative_surface_path_is_resolved_against_the_shape_file(tmp_path):
    stl = write_stl(tmp_path)
    path = tmp_path / "cube.shape"
    a_description({"top": FileSurface(stl)}).save(str(path))

    loaded = MappedShapeDescription.load(str(path))

    assert isinstance(loaded.surfaces["top"], FileSurface)
    assert loaded.surfaces["top"].path == stl


def test_a_file_surface_is_a_usable_triangulated_surface(tmp_path):
    surface = FileSurface(write_stl(tmp_path))

    closest = surface.get_closest_point([10.0, 0.0, 0.0])

    assert np.allclose(closest[0], 0.5)       # trimesh's default box spans -0.5 .. 0.5
