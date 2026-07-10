"""Float parameters — named numbers the parametric model is built on.

A `Parameter` is a `ValueStep` whose output is a single float expression (like every numeric
field: `86`, `bore*1.1`, `deg2rad(90)`). Unlike other steps it is **not** referenced by
identity — its *name* enters the expression namespace, so any downstream numeric field can
read it (`bore/2`, `pi*r`). Parameters may build on earlier parameters (they see the ones
above them). Codegen emits a plain `name = <expr>` assignment, exactly how a hand-written
parametric script leads with its driving numbers; the expression is emitted verbatim, so no
special codegen is needed (`ValueStep` already writes `name = <value>`).

Because the reference is by *name in a string*, it is invisible to the identity-based
forward-ref guard: a field that reads a parameter defined below it (or a deleted one) simply
fails to build and drops from the preview, the same best-effort behaviour as any bad
expression. That is intentional — no new machinery.
"""

from .base import ValueStep, eval_expr


class Parameter(ValueStep):
    default_name = "param"
    category = ("References",)  # a plain named number, alongside the other reference inputs
    label = "Float"
    SCHEMA = {
        "value": {"kind": "float", "label": "Value", "default": "1.0"},
    }

    def build(self, context):
        """Evaluate the expression (over parameters defined above, so parameters compose) and
        publish it under this step's name for downstream expression fields."""
        value = eval_expr(self.values["value"], context.params)
        context.params[self.name] = value
        context[self] = value
        return value
