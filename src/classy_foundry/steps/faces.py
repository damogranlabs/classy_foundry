"""Shared solid sub-element references — picking a face or an edge by clicking it, uniformly
across operations and shapes/stacks.

The viewport renders a solid as the side quads of *all* its operations (a bare op = 6, a shape
= `len(operations) × 6`; see view.display), so a single flat index addresses everything: the
operation (`operations_of(value)[index // stride]`) and the local element (`index % stride`).
`SolidRef` captures exactly that — a step reference and the int — so it pickles and resolves
lazily; `FaceRef` (stride 6, six sides) and `EdgeRef` (stride 12, twelve block edges) differ
only in the stride and how they name/apply their element. Features riding on faces: `SetPatch`,
`ExtractFace`, `Connector`; on edges: the per-kind `EdgeStep`s.
"""

from dataclasses import dataclass
from typing import ClassVar

from classy_blocks.util import constants

from .base import Step

# The six operation faces in classy_blocks' orientation order — also the order the viewport
# renders an operation's side quads, so a picked face index maps straight to its side.
SIDES = ["bottom", "top", "left", "right", "front", "back"]
# The twelve block edges as corner pairs, in classy_blocks' canonical order — the analogue of
# SIDES for edges, so a picked edge index maps straight to its two corners.
EDGE_PAIRS = constants.EDGE_PAIRS


def operations_of(value):
    """The classy_blocks operations behind a built value, uniformly: a shape/stack exposes
    them via `.operations`; a bare operation *is* its own single operation."""
    return getattr(value, "operations", [value])


def is_face_source(step) -> bool:
    """A step whose faces/edges can be picked: any solid — operation, shape, or a copy of
    either (all render side quads)."""
    return step.render_kind in ("operation", "shape", "element")


@dataclass
class SolidRef:
    """One picked sub-element of a solid: the step that drew it plus the flat index into that
    step's per-operation elements. Resolves lazily — to the live operation at build, to source
    at codegen — so it carries no cb geometry and pickles as a step reference + an int. The
    `stride` (elements per operation) is the only thing FaceRef/EdgeRef differ on."""

    step: Step
    index: int
    stride: ClassVar[int]

    @property
    def op_index(self) -> int:
        return self.index // self.stride

    @property
    def local(self) -> int:
        return self.index % self.stride

    def _operation(self, context):
        return operations_of(context[self.step])[self.op_index]

    def _operation_expr(self) -> str:
        """Source for this element's operation (a shape addresses it through `.operations[i]`)."""
        if self.step.render_kind == "shape":
            return f"{self.step.name}.operations[{self.op_index}]"
        return self.step.name


class FaceRef(SolidRef):
    """One picked face: `index` is a flat index into a solid's rendered side quads."""

    stride = len(SIDES)

    def side(self) -> str:
        return SIDES[self.local]

    def face(self, context):
        """The live classy_blocks Face this reference points at."""
        return self._operation(context).get_face(self.side())

    def face_expr(self) -> str:
        return f"{self._operation_expr()}.get_face({self.side()!r})"

    def patch_line(self, name: str) -> str:
        return f"{self._operation_expr()}.set_patch({self.side()!r}, {name!r})"

    def apply_patch(self, context, name: str) -> None:
        """Tag this face on its live operation. Silently skips a face whose operation no
        longer exists (an upstream edit shifted the indexing) — see-and-fix, not guarded."""
        value = context.get(self.step)
        if value is not None and self.op_index < len(operations_of(value)):
            operations_of(value)[self.op_index].set_patch(self.side(), name)


class EdgeRef(SolidRef):
    """One picked block edge: `index` is a flat index into a solid's twelve-per-operation
    edges. The two corners come from `EDGE_PAIRS[local]` — the arguments to `add_edge`."""

    stride = len(EDGE_PAIRS)

    def corners(self) -> tuple:
        return EDGE_PAIRS[self.local]

    def add_edge_line(self, data_expr: str) -> str:
        corner_1, corner_2 = self.corners()
        return f"{self._operation_expr()}.add_edge({corner_1}, {corner_2}, {data_expr})"

    def apply_edge(self, context, data) -> None:
        """Set this edge's data on its live operation. Silently skips an edge whose operation
        no longer exists (an upstream edit shifted the indexing) — see-and-fix, not guarded."""
        value = context.get(self.step)
        if value is not None and self.op_index < len(operations_of(value)):
            corner_1, corner_2 = self.corners()
            operations_of(value)[self.op_index].add_edge(corner_1, corner_2, data)
