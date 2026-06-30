"""Shared face primitives — picking a face by clicking it, uniformly across operations and
shapes/stacks.

The viewport renders an operation as its six side quads and a shape as `len(operations) × 6`
(see view.display), so a single picked face index addresses everything: the operation
(`operations_of(value)[index // 6]`) and the side (`SIDES[index % 6]`). A `FaceRef` stores
just that — a step reference and the int — so it pickles and resolves lazily. Three features
ride on it: `SetPatch` (name the faces), `ExtractFace` (reuse a face as a profile), and
`Connector` (loft between two faces).
"""

from dataclasses import dataclass

from .base import Step

# The six operation faces in classy_blocks' orientation order — also the order the viewport
# renders an operation's side quads, so a picked face index maps straight to its side.
SIDES = ["bottom", "top", "left", "right", "front", "back"]


def operations_of(value):
    """The classy_blocks operations behind a built value, uniformly: a shape/stack exposes
    them via `.operations`; a bare operation *is* its own single operation."""
    return getattr(value, "operations", [value])


def is_face_source(step) -> bool:
    """A step whose faces can be picked: any solid — operation, shape, or a copy of either
    (all render side quads)."""
    return step.render_kind in ("operation", "shape", "element")


@dataclass
class FaceRef:
    """One picked face: the step that drew it plus the flat face index into that step's
    rendered side quads. Resolves lazily — to the live operation/face at build, to source at
    codegen — so it carries no cb geometry and pickles as a step reference + an int."""

    step: Step
    index: int

    def side(self) -> str:
        return SIDES[self.index % len(SIDES)]

    def _operation(self, context):
        return operations_of(context[self.step])[self.index // len(SIDES)]

    def face(self, context):
        """The live classy_blocks Face this reference points at."""
        return self._operation(context).get_face(self.side())

    # --- source generation (a shape addresses its operation through `.operations[i]`) ---

    def _operation_expr(self) -> str:
        if self.step.render_kind == "shape":
            return f"{self.step.name}.operations[{self.index // len(SIDES)}]"
        return self.step.name

    def face_expr(self) -> str:
        return f"{self._operation_expr()}.get_face({self.side()!r})"

    def patch_line(self, name: str) -> str:
        return f"{self._operation_expr()}.set_patch({self.side()!r}, {name!r})"

    def apply_patch(self, context, name: str) -> None:
        """Tag this face on its live operation. Silently skips a face whose operation no
        longer exists (an upstream edit shifted the indexing) — see-and-fix, not guarded."""
        value = context.get(self.step)
        if value is None:
            return
        operations = operations_of(value)
        op_index = self.index // len(SIDES)
        if op_index < len(operations):
            operations[op_index].set_patch(self.side(), name)
