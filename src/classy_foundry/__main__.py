"""CLI entry point: `python -m classy_foundry [file.shape] [surface.stl ...]`.

The editor is a terminal program. A meshing script never imports foundry; it reads the
`.shape` file with `MappedShapeDescription.load` and hands the result to `cb.MappedShape`.

Surfaces named on the command line are loaded as backdrops -- to view and to snap points
onto. They are saved with the document, so the arguments are needed only the first time;
afterwards a surface can also be **dragged onto the window**.
"""

import sys

import polyscope as ps
import polyscope.imgui as psim

from . import storage
from .document import Document
from .view import keymap, patches, scene
from .view.editor import Editor
from .view.navigator import Navigator, draw_settings


def load_surfaces(document: Document, paths) -> None:
    """Each file becomes a backdrop patch named after it; re-loading one re-points that
    same patch instead of adding another."""
    for path in paths:
        document.surface_patch(path)


def main(argv: list) -> None:
    path = argv[0] if argv else "untitled.shape"
    editor = Editor(storage.load(path), path)
    load_surfaces(editor.document, argv[1:])

    ps.init()
    ps.set_up_dir("z_up")
    ps.set_open_imgui_window_for_user_callback(False)
    scene.sync(editor.document, editor.selection, editor.move)
    # A SpaceMouse if spacenavd is running, else None -- it drives the camera and nothing
    # else, so its absence changes nothing about the editor.
    navigator = Navigator.attach(distance=editor.document.extent * 2.0)

    def dropped(paths) -> None:
        """Polyscope hands us whatever was dragged onto the window."""
        load_surfaces(editor.document, paths)
        scene.sync(editor.document, editor.selection, editor.move)

    def callback() -> None:
        keymap.draw_help()
        psim.SetNextWindowSize((320, 320), psim.ImGuiCond_FirstUseEver)
        resync = False
        if psim.Begin("classy_foundry"):
            psim.Text(path)
            psim.Text(f"{len(editor.document.points)} points, {len(editor.document.cells)} blocks")
            psim.Text(f"selected: {len(editor.selection)}")
            psim.Separator()
            resync = patches.draw(editor)
            psim.Separator()
            draw_settings(navigator)
        psim.End()
        for device in filter(None, [navigator]):
            device.step(editor.document.extent)
        if editor.handle_frame() or resync:
            scene.sync(editor.document, editor.selection, editor.move)

    ps.set_files_dropped_callback(dropped)
    ps.set_user_callback(callback)
    ps.show()


if __name__ == "__main__":
    main(sys.argv[1:])
