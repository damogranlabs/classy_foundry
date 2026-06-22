"""Automatic graders — fill in every cell count the manual chops left unset.

Each is a `HelperStep`: `name = cb.SomeGrader(mesh, args…)` then `name.grade()`. A grader
acts on the whole assembled mesh and grades only the still-ungraded rows, so a manual
`Chop` (a specific axis) and a grader (everything else) compose. This is what lets a Shape
or catalogue solid write a blockMeshDict without hand-chopping every axis.
"""

from .base import HelperStep


class GraderStep(HelperStep):
    """Shared attrs for the automatic graders (their own Grading submenu)."""

    cb_call = "grade"
    default_name = "grader"
    category = ("Grading", "Automatic")


class FixedCount(GraderStep):
    cb_name = "FixedCountGrader"
    label = "Fixed count"
    SCHEMA = {
        "count": {"kind": "int", "label": "Cells per block", "default": "5"},
    }


class Simple(GraderStep):
    cb_name = "SimpleGrader"
    label = "Simple"
    SCHEMA = {
        "cell_size": {"kind": "float", "label": "Cell size", "default": "0.1"},
        "take": {"kind": "choice", "label": "Take", "default": "avg",
                 "choices": ["avg", "min", "max"]},
    }


class Inflation(GraderStep):
    cb_name = "InflationGrader"
    label = "Inflation"
    SCHEMA = {
        "first_cell_size": {"kind": "float", "label": "First cell size", "default": "0.01"},
        "bulk_cell_size": {"kind": "float", "label": "Bulk cell size", "default": "0.1"},
    }
