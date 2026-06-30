"""'STL surface' step — load an STL and show it as reference geometry.

Pure scaffolding for now: classy_blocks references a surface by *path* (a blockMeshDict
`searchableSurface`), not by its loaded mesh, so the loaded triangles are only for the
viewport — a backdrop to build against instead of in thin air. It adds nothing to the mesh
and emits no script (reference-only); **projection** will later wire the path into codegen.
"""

from ..geom import load_stl
from .base import Step


class Surface(Step):
    category = ("References",)
    default_name = "surface"
    label = "STL surface"
    render_kind = "surface"
    SCHEMA = {
        "file": {"kind": "text", "label": "STL file", "default": ""},
    }

    def build(self, context):
        path = self.values["file"]
        if path:  # load failures are swallowed by model.build → the surface simply won't show
            context[self] = load_stl(path)
        return context.get(self)

    def to_lines(self):
        return []  # reference-only until projection references the path
