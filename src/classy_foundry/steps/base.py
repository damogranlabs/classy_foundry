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

# kind -> Python-literal codegen. Pairs with the view's kind -> widget registry.
# `point`/`point_list` codegen each entry via _point_code (a name for a ref, else a list).
CODEGEN = {
    "point3": lambda v: repr([float(x) for x in v]),
    "float": lambda v: repr(float(v)),
    "int": lambda v: repr(int(v)),
    "point": lambda v: _point_code(v),
    "point_list": lambda v: "[" + ", ".join(_point_code(e) for e in v) + "]",
    "index_list": lambda v: repr([[int(i) for i in row] for row in v]),
    "ref": lambda step: step.name if step is not None else "None",
}


class Step:
    cb_name: str = ""
    default_name: str = "step"
    adds_to_mesh: bool = False
    SCHEMA: dict = {}
    category: tuple = ()   # palette path, e.g. ("Solids", "Simple"); nests into submenus
    label: str = ""        # palette menu label (falls back to the class name)
    render_kind = None     # view.display dispatch key (e.g. "operation"); None = not drawn

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
}

# kind -> stored value turned into a live cb argument at build time
RESOLVE = {
    "ref": lambda v, ctx: ctx[v],
    "point": _resolve_point,
    "point_list": lambda v, ctx: [_resolve_point(e, ctx) for e in v],
}


class ProducingStep(Step):
    """A step that constructs a new value: `name = cb.X(args...)`."""

    def build(self, context):
        args = [self._resolve(self.values[f], spec, context) for f, spec in self.SCHEMA.items()]
        value = getattr(cb, self.cb_name)(*args)
        context[self] = value
        return value

    @staticmethod
    def _resolve(value, spec, context):
        resolver = RESOLVE.get(spec["kind"])
        return resolver(value, context) if resolver else value

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
        getattr(target, self.cb_method)(**{f: self.values[f] for f, _ in self._kwargs_fields()})
        context[self] = target
        return target

    def to_lines(self):
        target = self._target()
        kwargs = ", ".join(f"{f}={CODEGEN[spec['kind']](self.values[f])}" for f, spec in self._kwargs_fields())
        name = target.name if target is not None else "None"
        return [f"{name}.{self.cb_method}({kwargs})"]


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
