"""Document <-> `MappedShapeDescription`.

**The only module that knows about indices.** Above it the topology is an object graph, so
adding or deleting a point renumbers nothing; below it classy_blocks wants integers. The
translation is a single enumeration each way.
"""

import os

import numpy as np

from .description import FileSurface, MappedShapeDescription
from .document import Document


def to_description(document: Document) -> MappedShapeDescription:
    number = {point: index for index, point in enumerate(document.points)}
    surfaced = [patch for patch in document.patches if patch.surface]
    return MappedShapeDescription(
        points=np.asarray([point.position for point in document.points], dtype=float).reshape(-1, 3),
        hexas=[[number[point] for point in cell.points] for cell in document.cells],
        patches={patch.name: [[number[point] for point in face] for face in patch.faces]
                 for patch in document.patches},
        surfaces={patch.name: FileSurface(patch.surface) for patch in surfaced},
    )


def from_description(description: MappedShapeDescription) -> Document:
    document = Document()
    points = [document.add_point(position) for position in np.asarray(description.points, dtype=float)]
    for hexa in description.hexas:
        document.add_cell([points[index] for index in hexa])
    for name, faces in description.patches.items():
        surface = description.surfaces.get(name)
        patch = document.add_patch(name, surface=None if surface is None else surface.path)
        for face in faces:
            document.assign_face(patch, [points[index] for index in face])
    return document


def save(document: Document, path: str) -> None:
    to_description(document).save(path)


def load(path: str) -> Document:
    """The document in `path`, or an empty one when the file does not exist yet -- that is
    how `python -m classy_foundry new.shape` starts."""
    if not os.path.exists(path):
        return Document()
    return from_description(MappedShapeDescription.load(path))
