"""Optimizer steps — release mesh vertices and improve grid quality, on classy_blocks'
existing coordinate-addressed clamp API (no smart points; see design.md → Optimization).

Three step kinds, all in the existing taxonomy — no new machinery:

- **Optimizer** (`OptimizerStep`, a `ProducingStep`) — `optimizer = cb.SketchOptimizer(target)`.
  Its output is the optimizer object the clamp/optimize steps refer to; it draws nothing
  (`render_kind = None`) — its target already shows.
- **Clamp** (`ClampStep`, one subclass per clamp class) — `optimizer.add_clamp(cb.XClamp(point, …))`.
  A vertex is *fixed* by default; a clamp releases it and says how it may move. The clamped
  point is a `point` input (literal or a reference point picked with the dropper); cb matches
  that coordinate back to its vertex within tolerance. One subclass per clamp class, so *which*
  clamp is dispatch by type, not an `if`-ladder.
- **Optimize** (`Optimize`, a `ConfiguringStep`) — `optimizer.optimize(max_iterations=…)`. The
  expensive call: it runs only when the build is in `optimize` mode (the Run button / write),
  so the live viewport stays responsive; codegen always emits it (never baked coordinates).

The optimizer mutates its target sketch in place at `optimize()` time; every rebuild
reconstructs the prefix from source, so re-running never compounds and "undo" is just the
rollback marker before the optimize step. Shape/Mesh optimizers wait on their own wrinkles
(`ShapeOptimizer` wants `shape.operations`; `MeshOptimizer` is mesh-targeted) — deferred.
"""

import classy_blocks as cb

from .base import CODEGEN, ConfiguringStep, ProducingStep, resolve_value
from .curve import CurveStep
from .sketches import SketchStep


class OptimizerStep(ProducingStep):
    """Marker base: a step whose output is a classy_blocks optimizer (the value clamp and
    optimize steps reference). Draws nothing — the target it optimizes already shows."""

    category = ("Optimizers",)
    default_name = "optimizer"
    render_kind = None


class SketchOptimizer(OptimizerStep):
    cb_name = "SketchOptimizer"
    label = "Sketch optimizer"
    SCHEMA = {
        "sketch": {"kind": "ref", "label": "Sketch", "default": None, "accepts": SketchStep},
    }


class ClampStep(ConfiguringStep):
    """Releases one vertex for the optimizer: `optimizer.add_clamp(cb.XClamp(args…))`.

    The `optimizer` ref field names the target; every other schema field is a positional
    argument to the clamp constructor (`clamp_name`), the first being the clamped point.
    Reuses `ConfiguringStep` for the in-place "output = target" semantics and the reference
    plumbing, overriding only the target lookup (the optimizer field may sit beside a second
    geometry ref) and the wrap-in-a-constructor build/codegen.
    """

    clamp_name: str = ""
    category = ("Optimizers", "Clamps")
    default_name = "clamp"
    SCHEMA: dict = {}

    def _target(self):
        return self.values["optimizer"]

    def _arg_fields(self):
        return [(f, spec) for f, spec in self.SCHEMA.items() if f != "optimizer"]

    def build(self, context):
        optimizer = context[self._target()]
        args = [resolve_value(self.values[f], spec, context) for f, spec in self._arg_fields()]
        optimizer.add_clamp(getattr(cb, self.clamp_name)(*args))
        context[self] = optimizer
        return optimizer

    def to_lines(self):
        target = self._target()
        args = ", ".join(CODEGEN[spec["kind"]](self.values[f]) for f, spec in self._arg_fields())
        name = target.name if target is not None else "None"
        return [f"{name}.add_clamp(cb.{self.clamp_name}({args}))"]


_OPTIMIZER = {"kind": "ref", "label": "Optimizer", "default": None, "accepts": OptimizerStep}
_POINT = {"kind": "point", "default": [0.0, 0.0, 0.0]}


class FreeClamp(ClampStep):
    clamp_name = "FreeClamp"
    label = "Free clamp"
    SCHEMA = {
        "optimizer": _OPTIMIZER,
        "position": {**_POINT, "label": "Point"},
    }


class LineClamp(ClampStep):
    clamp_name = "LineClamp"
    label = "Line clamp"
    SCHEMA = {
        "optimizer": _OPTIMIZER,
        "position": {**_POINT, "label": "Point"},
        "point_1": {**_POINT, "label": "Line start"},
        "point_2": {**_POINT, "label": "Line end"},
    }


class PlaneClamp(ClampStep):
    clamp_name = "PlaneClamp"
    label = "Plane clamp"
    SCHEMA = {
        "optimizer": _OPTIMIZER,
        "position": {**_POINT, "label": "Point"},
        "point": {**_POINT, "label": "Plane origin"},
        "normal": {"kind": "point3", "label": "Plane normal", "default": [0.0, 0.0, 1.0]},
    }


class RadialClamp(ClampStep):
    clamp_name = "RadialClamp"
    label = "Radial clamp (circle)"
    SCHEMA = {
        "optimizer": _OPTIMIZER,
        "position": {**_POINT, "label": "Point"},
        "center": {**_POINT, "label": "Centre"},
        "normal": {"kind": "point3", "label": "Axis", "default": [0.0, 0.0, 1.0]},
    }


class CurveClamp(ClampStep):
    clamp_name = "CurveClamp"
    label = "Curve clamp"
    SCHEMA = {
        "optimizer": _OPTIMIZER,
        "position": {**_POINT, "label": "Point"},
        "curve": {"kind": "ref", "label": "Curve", "default": None, "accepts": CurveStep},
    }


class Optimize(ConfiguringStep):
    """Runs the optimization: `optimizer.optimize(max_iterations=…)`. The expensive call, so
    it executes only when the build is in `optimize` mode (the Run button / write/export);
    the live viewport builds the optimizer (and its clamps) but skips this. Codegen always
    emits it — the exported script recomputes faithfully, only the GUI preview defers it."""

    cb_method = "optimize"
    category = ("Optimizers",)
    default_name = "optimize"
    label = "Optimize (run)"
    SCHEMA = {
        "optimizer": {"kind": "ref", "label": "Optimizer", "default": None, "accepts": OptimizerStep},
        "max_iterations": {"kind": "int", "label": "Iterations", "default": "20"},
    }

    def build(self, context):
        if context.optimize:
            return super().build(context)
        context[self] = context[self._target()]  # construct-only preview: defer the work
        return context[self]
