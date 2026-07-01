"""Host-independent step base: a schema-driven recipe around a classy_blocks construct.

A **step** is one statement in the recipe. It has a user-facing `name` (its script
variable), typed inputs declared by `SCHEMA`, builds a live classy_blocks value, and
emits its own source via `to_lines()`. No live `cb` geometry is stored on a step, so
the pickle is just the recipe (scalars + references by identity).

`SCHEMA` field order is the constructor's positional-argument order. A field's `kind`
is a scalar (`point3` / `float` / `int` / `index_list`), a whole-field `ref` to an
ancestor step, or a **point input** (`point` / `point_list`). A point input's value is
either a literal `[x, y, z]` *or* a `Point` step (a per-entry reference) — both resolve
to coordinates. References are stored by **identity**; codegen emits the step's *current*
name, so renaming is always safe.

`Step` is abstract; concrete steps subclass `ProducingStep` (`name = cb.X(...)`),
`ConfiguringStep` (`<ref>.method(...)`), or `ValueStep` (`name = <literal>`).
"""

import classy_blocks as cb
import numpy

# A scalar numeric field's value is an **expression string** (e.g. "pi/2", "deg2rad(90)"),
# evaluated in this math-only namespace for the live value and emitted verbatim in codegen
# (so the script reads like hand-written classy_blocks). The same names are imported by the
# exported script (see `expr_import_line`).
_EXPR_NAMES = (
    "pi",
    "e",
    "sin",
    "cos",
    "tan",
    "arcsin",
    "arccos",
    "arctan",
    "arctan2",
    "sqrt",
    "exp",
    "log",
    "radians",
    "degrees",
    "deg2rad",
    "abs",
)
EXPR_NAMESPACE = {name: getattr(numpy, name) for name in _EXPR_NAMES}


def eval_expr(value):
    """Evaluate a numeric field's expression string; pass numbers through unchanged
    (defaults / legacy pickles). Raises on a bad expression, so a mid-edit step just
    fails to build (best-effort) until it parses again."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(eval(value, {"__builtins__": {}}, EXPR_NAMESPACE))


def expr_import_line():
    """The import the exported script needs so emitted expressions resolve."""
    return "from numpy import " + ", ".join(_EXPR_NAMES)


def load_points(path):
    """Read an (N, 3) point array from a whitespace/CSV text file (e.g. an airfoil)."""
    return numpy.loadtxt(path)


# kind -> Python-source codegen. Pairs with the view's kind -> widget registry.
# `float`/`int` are expression strings, emitted verbatim. `point`/`point_list` codegen each
# entry via _point_code (a name for a ref, else a list).
CODEGEN = {
    "point3": lambda v: repr([float(x) for x in v]),
    "float": lambda v: str(v),
    "int": lambda v: str(v),
    "point": lambda v: _point_code(v),
    "point_list": lambda v: "[" + ", ".join(_point_code(e) for e in v) + "]",
    "index_list": lambda v: repr([[int(i) for i in row] for row in v]),
    "points_file": lambda v: f"np.loadtxt({v!r})",
    "text": lambda v: repr(v),
    "choice": lambda v: repr(v),
    "ref": lambda step: step.name if step is not None else "None",
}


class BuildContext(dict):
    """The `{step: cb_value}` map a replay fills, plus the `optimize` flag that gates the
    expensive optimizer pass. It behaves like the plain dict every `build()` already uses
    (identity-keyed by step); the flag rides alongside so the one step that cares — the
    optimize step — reads `context.optimize` instead of threading a parameter through every
    `build()`. False for the live viewport (optimizers construct but skip `optimize()`),
    True for write/export."""

    def __init__(self, optimize: bool = False):
        super().__init__()
        self.optimize = optimize


class Step:
    cb_name: str = ""
    default_name: str = "step"
    adds_to_mesh: bool = False
    SCHEMA: dict = {}
    category: tuple = ()  # palette path, e.g. ("Solids", "Simple"); nests into submenus
    label: str = ""  # palette menu label (falls back to the class name)
    render_kind = None  # view.display dispatch key (e.g. "operation"); None = not drawn
    AXIS = None  # (origin_field, direction_field) -> a point-and-vector axis cue; None = none

    def __init__(self, name="", **values):
        self.name = name
        self.values = {field: self._default(spec) for field, spec in self.SCHEMA.items()}
        self.values.update({k: v for k, v in values.items() if k in self.SCHEMA})

    @staticmethod
    def _default(spec):
        default = spec["default"]
        return list(default) if isinstance(default, (list, tuple)) else default

    def references(self):
        """The ancestor steps this step refers to (by identity), across all field kinds."""
        refs = []
        for field, spec in self.SCHEMA.items():
            refs += REF_EXTRACT.get(spec["kind"], _no_refs)(self.values[field])
        return refs

    def build(self, context):
        """Build/configure this step's live `cb` value into `context[self]`; return it."""
        raise NotImplementedError

    def to_lines(self):
        """This step's classy_blocks source line(s)."""
        raise NotImplementedError

    def apply_to_mesh(self, mesh, context):
        """Mesh-level hook, run once per step after every `mesh.add` (see model.build_mesh).
        A no-op for element steps; mesh-level steps (graders, …) override it."""


# --- point inputs: a value is either a literal [x, y, z] or a Point step (a reference) ---


def _is_ref(entry):
    return isinstance(entry, Step)


def _point_code(entry):
    return entry.name if _is_ref(entry) else repr([float(x) for x in entry])


def _resolve_point(entry, context):
    return context[entry] if _is_ref(entry) else entry


def _no_refs(_value):
    return []


# kind -> referenced ancestor steps held in a field value
REF_EXTRACT = {
    "ref": lambda v: [v] if v is not None else [],
    "point": lambda v: [v] if _is_ref(v) else [],
    "point_list": lambda v: [e for e in v if _is_ref(e)],
    "face": lambda v: [v.step] if v is not None else [],
    "face_list": lambda v: [face.step for face in v],
}

# kind -> stored value turned into a live cb argument at build time
RESOLVE = {
    "ref": lambda v, ctx: ctx[v],
    "point": _resolve_point,
    "point_list": lambda v, ctx: [_resolve_point(e, ctx) for e in v],
    "float": lambda v, ctx: eval_expr(v),
    "int": lambda v, ctx: int(eval_expr(v)),
    "points_file": lambda v, ctx: load_points(v),
}


def resolve_value(value, spec, context):
    """A stored field value -> its live cb argument (eval'd expr, resolved ref, …).
    Kinds with no resolver (point3, index_list) pass through unchanged."""
    resolver = RESOLVE.get(spec["kind"])
    return resolver(value, context) if resolver else value


class ProducingStep(Step):
    """A step that constructs a new value: `name = cb.X(args...)`."""

    def build(self, context):
        args = [resolve_value(self.values[f], spec, context) for f, spec in self.SCHEMA.items()]
        value = getattr(cb, self.cb_name)(*args)
        context[self] = value
        return value

    def to_lines(self):
        args = ", ".join(CODEGEN[spec["kind"]](self.values[f]) for f, spec in self.SCHEMA.items())
        return [f"{self.name} = cb.{self.cb_name}({args})"]


class ConfiguringStep(Step):
    """A step that calls a method on an ancestor in place: `<ref>.method(kwargs…)`.

    Exactly one `ref` field names the target; every other field becomes a keyword
    argument to `cb_method`. The output *is* the (now-configured) target, so later
    steps can reference either it or this step interchangeably.
    """

    cb_method: str = ""

    def _target(self):
        return next(self.values[f] for f, spec in self.SCHEMA.items() if spec["kind"] == "ref")

    def _kwargs_fields(self):
        return [(f, spec) for f, spec in self.SCHEMA.items() if spec["kind"] != "ref"]

    def build(self, context):
        target = context[self._target()]
        kwargs = {
            f: resolve_value(self.values[f], spec, context) for f, spec in self._kwargs_fields()
        }
        getattr(target, self.cb_method)(**kwargs)
        context[self] = target
        return target

    def to_lines(self):
        target = self._target()
        kwargs = ", ".join(
            f"{f}={CODEGEN[spec['kind']](self.values[f])}" for f, spec in self._kwargs_fields()
        )
        name = target.name if target is not None else "None"
        return [f"{name}.{self.cb_method}({kwargs})"]


class DerivedStep(ConfiguringStep):
    """Like `ConfiguringStep` but the method *returns a new value* bound to this step's name:
    `name = <ref>.method(kwargs…)` (a point on a curve, an extracted face, …). The target is
    left unchanged; the output is the returned value. Reuses ConfiguringStep's ref/kwargs
    plumbing (`_target`, `_kwargs_fields`), overriding only build (assigns the result) and
    codegen (assigns to `name`)."""

    def build(self, context):
        target = context[self._target()]
        kwargs = {
            f: resolve_value(self.values[f], spec, context) for f, spec in self._kwargs_fields()
        }
        context[self] = getattr(target, self.cb_method)(**kwargs)
        return context[self]

    def to_lines(self):
        target = self._target()
        kwargs = ", ".join(
            f"{f}={CODEGEN[spec['kind']](self.values[f])}" for f, spec in self._kwargs_fields()
        )
        name = target.name if target is not None else "None"
        return [f"{self.name} = {name}.{self.cb_method}({kwargs})"]


class ValueStep(Step):
    """A step whose output is a literal value bound to a name: `name = <value>`.

    Its single `SCHEMA` field holds that value — e.g. a reference point's coordinates.
    classy_blocks has no constructor for these; they are plain variables other steps
    reference, exactly as in a hand-written script.
    """

    def _field(self):
        return next(iter(self.SCHEMA))

    def build(self, context):
        context[self] = self.values[self._field()]
        return context[self]

    def to_lines(self):
        field = self._field()
        return [f"{self.name} = {CODEGEN[self.SCHEMA[field]['kind']](self.values[field])}"]


class HelperStep(Step):
    """A step that wraps the mesh in a classy_blocks helper and calls a finishing method:
    `name = cb.Cls(mesh, args…)` then `name.<cb_call>()`.

    The shared shape of the auto-graders (and, later, mesh optimizers/smoothers — element-
    targeted helpers will add a `ref` target, clamp-carrying ones their own body). The
    helper acts on the whole assembled mesh, so it does its work in `apply_to_mesh` (run
    after every `mesh.add`), not in the per-step build pass, and produces no display
    geometry. Every `SCHEMA` field is a positional constructor arg after `mesh`.
    """

    cb_call: str = ""

    def build(self, context):
        """No pre-assembly value to build; the helper runs later, in apply_to_mesh."""
        return None

    def _args(self, context):
        return [resolve_value(self.values[f], spec, context) for f, spec in self.SCHEMA.items()]

    def apply_to_mesh(self, mesh, context):
        helper = getattr(cb, self.cb_name)(mesh, *self._args(context))
        getattr(helper, self.cb_call)()

    def to_lines(self):
        args = ", ".join(
            ["mesh"] + [CODEGEN[spec["kind"]](self.values[f]) for f, spec in self.SCHEMA.items()]
        )
        return [f"{self.name} = cb.{self.cb_name}({args})", f"{self.name}.{self.cb_call}()"]
