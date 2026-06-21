"""Entry point: `python app.py` (from this directory)."""

import polyscope as ps
import polyscope.imgui as psim

from .model import Model
from .steps.box import Box
from .steps.mapped_sketch import MappedSketch
from .view.display import sync_display
from .view.panel import draw_panel
from .view.picker import handle_pick
from .view.selection import sync_selection
from .view.sketch_editor import SketchEditor


def main():
    model = Model()
    sketch = model.add(MappedSketch("sketch0"))
    model.add(Box("box0", start_point=[2.0, 0.0, 0.0], diagonal_point=[3.0, 1.0, 1.0]))

    sketch_editor = SketchEditor()
    session = {"active": sketch}

    ps.init()
    ps.set_up_dir("z_up")
    ps.set_open_imgui_window_for_user_callback(False)  # we draw our own resizable window
    dirty = {"flag": True}

    def callback():
        psim.SetNextWindowSize((360, 640), psim.ImGuiCond_FirstUseEver)
        changed = False
        if psim.Begin("classy_polyscope"):
            changed = draw_panel(model, sketch_editor, session)
        psim.End()
        active = session.get("active")
        if session.get("pick") is not None:
            changed |= handle_pick(model, session)  # ref-pick mode
        elif active is sketch_editor.sketch and sketch_editor.mode is not None:
            changed |= sketch_editor.handle_click()  # sketch placement mode
        else:
            sync_selection(model, session)  # idle: viewport -> list
        if changed or dirty["flag"]:
            sync_display(model, overlay=sketch_editor.render_overlay)
            dirty["flag"] = False

    ps.set_user_callback(callback)
    ps.show()


if __name__ == "__main__":
    main()
