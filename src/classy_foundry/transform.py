"""The modal move, Blender's `G`: a set of points, a constraint, and the positions they
started from.

It knows nothing about mice, rays or polyscope -- the view solves a ray into a world
position with the constraint and hands it to `to()`. That is also why a later extrude can
reuse it verbatim on points it has just created.
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np


@dataclass
class Move:
    points: list
    constraint: object
    origins: list = field(default_factory=list)
    reference: Optional[np.ndarray] = None

    @classmethod
    def start(cls, points: Sequence, constraint) -> "Move":
        return cls(list(points), constraint, [np.array(p.position, dtype=float) for p in points])

    @property
    def centroid(self) -> np.ndarray:
        """Of the *original* positions, so re-constraining mid-move stays anchored where
        the grab began."""
        return np.mean(self.origins, axis=0)

    def set_constraint(self, constraint) -> None:
        """Switch axis/plane mid-move. The drag restarts: positions go back to the
        originals and the next `to()` re-establishes the reference."""
        self.constraint, self.reference = constraint, None
        self._translate(np.zeros(3))

    def to(self, position) -> None:
        """`position` is the solved world point (constrained, possibly snapped). The first
        call only records where the drag started."""
        position = np.asarray(position, dtype=float)
        if self.reference is None:
            self.reference = position
        self._translate(position - self.reference)

    def by(self, distance: float) -> None:
        """Typed numeric entry; a plane answers with zero, so no branching here."""
        self._translate(self.constraint.offset(distance))

    def cancel(self) -> None:
        self._translate(np.zeros(3))

    def confirm(self) -> None:
        """Keep the current positions: the originals become them, so a stray later cancel
        cannot resurrect the old ones."""
        self.origins = [np.array(point.position, dtype=float) for point in self.points]

    def _translate(self, delta: np.ndarray) -> None:
        for point, origin in zip(self.points, self.origins):
            point.position = origin + delta
