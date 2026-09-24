"""`hex_faces` is pure index arithmetic, so it needs no GL context."""

import numpy as np

from classy_foundry.document import Document
from classy_foundry.view import scene
from classy_foundry.view.scene import _cell_colors, _point_colors, cell_owners, hex_faces


def unit_cube(document: Document) -> list:
    bottom = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    return [document.add_point(p) for p in bottom] + [document.add_point([x, y, 1]) for x, y, _ in bottom]


def test_a_hex_becomes_six_quads():
    document = Document()
    cell = document.add_cell(unit_cube(document))

    vertices, faces = hex_faces([cell])

    assert vertices.shape == (8, 3)
    assert faces.shape == (6, 4)


def test_a_quad_cell_becomes_one_quad():
    document = Document()
    quad = [document.add_point([x, y, 0]) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
    cell = document.add_cell(quad)

    vertices, faces = hex_faces([cell])

    assert vertices.shape == (4, 3)
    assert faces.tolist() == [[0, 1, 2, 3]]


def test_two_cells_are_offset_into_one_vertex_array():
    document = Document()
    first = document.add_cell(unit_cube(document))
    second = document.add_cell(unit_cube(document))

    vertices, faces = hex_faces([first, second])

    assert vertices.shape == (16, 3)
    assert faces.shape == (12, 4)
    assert faces[6:].min() == 8          # the second cell's faces address the second block


def test_no_cells_yields_empty_arrays():
    vertices, faces = hex_faces([])

    assert vertices.shape == (0, 3)
    assert faces.shape == (0, 4)
    assert np.issubdtype(faces.dtype, np.integer)


def test_only_the_selected_points_take_the_highlight_colour():
    document = Document()
    points = unit_cube(document)

    colors = _point_colors(points, [points[2], points[5]])

    assert np.allclose(colors[2], scene.SELECTED_COLOR)
    assert np.allclose(colors[5], scene.SELECTED_COLOR)
    assert np.allclose(colors[0], scene.POINT_COLOR)
    assert colors.shape == (8, 3)


def test_an_empty_selection_colours_every_point_the_same():
    document = Document()
    points = unit_cube(document)

    colors = _point_colors(points, [])

    assert np.allclose(colors, scene.POINT_COLOR)


def test_every_rendered_face_knows_which_block_it_belongs_to():
    """A pick reports a face index; this is how it becomes the block the user clicked."""
    document = Document()
    first = document.add_cell(unit_cube(document))
    second = document.add_cell(unit_cube(document))

    owners = cell_owners(document.cells)

    assert len(owners) == 12                       # six sides each
    assert owners[:6] == [first] * 6
    assert owners[6:] == [second] * 6


def test_a_quad_cell_owns_its_single_face():
    document = Document()
    quad = [document.add_point([x, y, 0]) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
    cell = document.add_cell(quad)

    assert cell_owners(document.cells) == [cell]


def test_only_the_selected_blocks_take_the_highlight_colour():
    document = Document()
    first = document.add_cell(unit_cube(document))
    document.add_cell(unit_cube(document))

    colors = _cell_colors(document.cells, [first])

    assert colors.shape == (12, 3)
    assert np.allclose(colors[:6], scene.SELECTED_CELL_COLOR)
    assert np.allclose(colors[6:], scene.CELL_COLOR)


def test_with_nothing_selected_every_block_looks_the_same():
    document = Document()
    document.add_cell(unit_cube(document))

    assert np.allclose(_cell_colors(document.cells, []), scene.CELL_COLOR)
