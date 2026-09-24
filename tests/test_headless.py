"""The view layer, driven without a GPU. Polyscope's user callback fires roughly once per
process in mock mode, so the inner draw functions are called directly inside a frame."""

import numpy as np
import polyscope as ps
import polyscope.imgui as psim
import pytest

from classy_foundry.document import Document
from classy_foundry.view import keymap, patches, scene
from classy_foundry.view.editor import Editor


@pytest.fixture(scope="module")
def mock_polyscope():
    ps.set_allow_headless_backends(True)
    ps.init("openGL_mock")
    ps.set_up_dir("z_up")
    yield
    ps.shutdown()


def a_document() -> Document:
    document = Document()
    cube = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    points = [document.add_point(p) for p in cube] + [document.add_point([x, y, 1]) for x, y, _ in cube]
    document.add_cell(points)
    patch = document.add_patch("top")
    document.assign_face(patch, points[4:])
    return document


def test_sync_registers_the_structures(mock_polyscope):
    scene.sync(a_document())

    assert ps.has_point_cloud(scene.POINTS_NAME)
    assert ps.has_surface_mesh(scene.CELLS_NAME)


def test_sync_survives_an_empty_document(mock_polyscope):
    scene.sync(Document())

    assert ps.has_point_cloud(scene.POINTS_NAME)


def test_the_patch_panel_draws_without_raising(mock_polyscope):
    editor = Editor(a_document())
    ps.frame_tick()

    if psim.Begin("test"):
        patches.draw(editor)
    psim.End()


def test_the_help_window_draws_without_raising(mock_polyscope):
    ps.frame_tick()

    keymap.draw_help()


def test_a_backdrop_patch_renders_its_surface(mock_polyscope, tmp_path):
    import trimesh

    stl = str(tmp_path / "hub.stl")
    trimesh.creation.box().export(stl)
    document = Document()
    document.add_patch("hub", surface=stl)      # a surface and no faces: a backdrop

    scene.sync(document)

    assert ps.has_surface_mesh("surface::hub")


def test_sync_colours_the_selection_and_survives_it(mock_polyscope):
    document = a_document()

    scene.sync(document, selection=[document.points[0]])

    assert ps.has_point_cloud(scene.POINTS_NAME)


def test_the_gizmo_appears_only_while_a_move_is_live(mock_polyscope):
    document = a_document()
    editor = Editor(document)
    editor.select(document.points[0], additive=False)

    scene.sync(document, editor.selection)
    assert not ps.has_curve_network(scene.GIZMO_NAME)

    editor.begin_move(view_normal=np.array([0.0, -1.0, 0.0]))
    scene.sync(document, editor.selection, editor.move)
    assert ps.has_curve_network(scene.GIZMO_NAME)

    editor.confirm_move()
    scene.sync(document, editor.selection, editor.move)
    assert not ps.has_curve_network(scene.GIZMO_NAME)


def test_the_gizmo_brightens_only_the_axis_the_constraint_allows(mock_polyscope):
    from classy_foundry.view.scene import _axis_colors

    editor = Editor(a_document())
    editor.select(editor.document.points[0], additive=False)
    editor.begin_move(view_normal=np.array([0.0, -1.0, 0.0]))
    editor.constrain("Y")

    colors = _axis_colors(editor.move.constraint)

    assert np.allclose(colors[1], scene.AXIS_COLORS[1])                  # Y at full strength
    assert np.allclose(colors[0], np.asarray(scene.AXIS_COLORS[0]) * scene.DIM)
    assert np.allclose(colors[2], np.asarray(scene.AXIS_COLORS[2]) * scene.DIM)


def test_a_surface_whose_file_has_gone_is_skipped_not_fatal(mock_polyscope):
    """Paths come from drops, the command line and a text field, so a moved STL must
    degrade to 'not shown' rather than raise on every frame."""
    document = Document()
    document.surface_patch("/nowhere/vanished.stl")

    scene.sync(document)                                  # must not raise

    assert not ps.has_surface_mesh("surface::vanished")


def test_a_dropped_surface_becomes_a_visible_backdrop(mock_polyscope, tmp_path):
    import trimesh

    stl = str(tmp_path / "blade.stl")
    trimesh.creation.box().export(stl)
    document = Document()

    document.surface_patch(stl)
    scene.sync(document)

    assert ps.has_surface_mesh("surface::blade")


def test_dropping_two_files_loads_both_as_backdrops(mock_polyscope, tmp_path):
    """What the drag-and-drop callback does with whatever Polyscope hands it."""
    import trimesh

    from classy_foundry.__main__ import load_surfaces

    paths = []
    for name in ("blade.stl", "hub.stl"):
        path = str(tmp_path / name)
        trimesh.creation.box().export(path)
        paths.append(path)
    document = Document()

    load_surfaces(document, paths)
    scene.sync(document)

    assert [patch.name for patch in document.patches] == ["blade", "hub"]
    assert ps.has_surface_mesh("surface::blade")
    assert ps.has_surface_mesh("surface::hub")


def test_the_patch_panel_reports_a_surface_whose_file_has_gone(mock_polyscope):
    document = Document()
    document.surface_patch("/nowhere/vanished.stl")
    ps.frame_tick()

    if psim.Begin("test"):
        patches.draw(Editor(document))                 # must not raise; shows the warning
    psim.End()


def test_sync_colours_selected_blocks(mock_polyscope):
    document = a_document()

    scene.sync(document, cells=document.cells)

    assert ps.has_surface_mesh(scene.CELLS_NAME)


def test_placing_and_moving_points_needs_no_gpu(mock_polyscope):
    editor = Editor(Document())
    point = editor.place_point([0.0, 0.0, 0.0])
    editor.select(point, additive=False)

    editor.begin_move(view_normal=np.array([0.0, -1.0, 0.0]))
    editor.constrain("X")
    editor.move.by(3.0)
    editor.confirm_move()

    assert np.allclose(point.position, [3.0, 0.0, 0.0])
