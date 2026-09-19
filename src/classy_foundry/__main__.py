"""CLI entry point: `python -m classy_foundry [file.shape]`.

The editor is a terminal program. A meshing script never imports foundry; it reads the
`.shape` file with `MappedShapeDescription.load` and hands the result to `cb.MappedShape`.
"""

import sys

import polyscope as ps
import polyscope.imgui as psim


def main(argv: list) -> None:
    path = argv[0] if argv else "untitled.shape"

    ps.init()
    ps.set_up_dir("z_up")
    ps.set_open_imgui_window_for_user_callback(False)

    def callback() -> None:
        psim.SetNextWindowSize((320, 480), psim.ImGuiCond_FirstUseEver)
        if psim.Begin("classy_foundry"):
            psim.Text(path)
        psim.End()

    ps.set_user_callback(callback)
    ps.show()


if __name__ == "__main__":
    main(sys.argv[1:])
