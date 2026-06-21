"""'Chop' step — grade one axis of an operation: `<op>.chop(axis=…, count=…)`.

The first configuring step. Targets any operation (a step that adds to the mesh); an
operation needs a chop on each of its three axes before the mesh can be written.
"""

from .base import ConfiguringStep


class Chop(ConfiguringStep):
    cb_method = "chop"
    default_name = "chop"
    category = ("Grading",)
    label = "Grade axis"
    SCHEMA = {
        "target": {"kind": "ref", "label": "Operation", "default": None,
                   "accepts": lambda step: step.adds_to_mesh},
        "axis": {"kind": "int", "label": "Axis (0/1/2)", "default": 0},
        "count": {"kind": "int", "label": "Cells", "default": 10},
    }
