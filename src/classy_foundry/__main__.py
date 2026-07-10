"""Entry point: `python app.py` (from this directory)."""

import polyscope as ps
import polyscope.imgui as psim

from .model import Model
from .steps.box import Box
from .steps.mapped_sketch import MappedSketch
from .view.cues import update_cues
from .view.display import sync_display
from .view.edges import draw_edges
from .view.panel import draw_panel
from .view.picker import handle_pick
from .view.sketch_editor import SketchEditor, draw_number_labels


def main():
    model = Model()
    box = model.add(Box("box0", start_point=[2.0, 0.0, 0.0], diagonal_point=[3.0, 1.0, 1.0]))

    sketch_editor = SketchEditor()
    session = {"active": box}

    ps.init()
    ps.set_up_dir("z_up")
    ps.set_open_imgui_window_for_user_callback(False)  # we draw our own resizable window
    sync_display(model, overlay=sketch_editor.render_overlay)  # initial render before show
    dirty = {"flag": True}

    def callback():
        psim.SetNextWindowSize((360, 640), psim.ImGuiCond_FirstUseEver)
        changed = False
        if psim.Begin("classy_polyscope"):
            changed = draw_panel(model, sketch_editor, session)
        psim.End()
        active = session.get("active")
        if session.get("pick") is not None:
            changed |= handle_pick(model, session)  # a pick button is armed: click fills the input
        elif active is sketch_editor.sketch and sketch_editor.mode is not None:
            changed |= sketch_editor.handle_click(model)  # sketch placement mode
        # normal mode: no viewport selection — the active step is chosen from the list only
        optimize = session.pop("run_optimize", False)  # one-shot Run; reverts on next rebuild
        if changed or dirty["flag"] or optimize:
            session["context"] = sync_display(model, overlay=sketch_editor.render_overlay,
                                              upto=session.get("marker"), optimize=optimize)
            dirty["flag"] = False
        update_cues(model, session)  # every frame: survives rebuilds, tracks same-structure re-clicks
        draw_edges(model, session)  # edge picking + kind/chop indicators, while an Edge step is active
        if isinstance(active, MappedSketch):  # point/block number overlay for the edited sketch
            draw_number_labels(active, session.get("context"))

    ps.set_user_callback(callback)
    ps.show()


if __name__ == "__main__":
    main()
