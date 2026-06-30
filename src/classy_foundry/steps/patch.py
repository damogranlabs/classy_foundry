"""'Set patch' step — name a boundary by clicking its faces: `op.set_patch(side, name)`.

A blockMeshDict writes with one default patch unless boundaries are named; naming them is
what turns the mesh into a runnable case (named boundaries carry the boundary conditions).

Rather than mirror classy_blocks' per-shape patch shortcuts (`set_outer_patch`,
`set_symmetry_patch`, … — which differ shape to shape), a patch here is **a name plus a set
of clicked faces** (a `face_list`), and the system derives each operation and side via
`FaceRef` (see `faces`). That is uniform across bare operations *and* shapes/stacks — no
shape-specific code, no `if` over kinds.
"""

from .base import Step
from .faces import is_face_source


class SetPatch(Step):
    category = ("Patches",)
    default_name = "patch"
    label = "Set patch"
    SCHEMA = {
        "faces": {"kind": "face_list", "label": "Faces", "default": [], "accepts": is_face_source},
        "name": {"kind": "text", "label": "Patch name", "default": "patch"},
    }

    def build(self, context):
        for face in self.values["faces"]:
            face.apply_patch(context, self.values["name"])
        context[self] = None
        return None

    def to_lines(self):
        return [face.patch_line(self.values["name"]) for face in self.values["faces"]]
