"""The document: one ordered list of steps.

Builds live classy_blocks values (best-effort, for display/write), exports a standalone
script (one-way codegen), and persists by pickling the steps (the recipe). No polyscope
import — pure logic. References between steps are by identity; the name is the script
variable, resolved at codegen time, so renaming is always safe.
"""

import keyword
import pickle

import classy_blocks as cb

from .steps.base import BuildContext, expr_import_line


class Model:
    def __init__(self):
        self.steps: list = []

    # ---- step list ----

    def add(self, step):
        if not step.name:
            step.name = self._unique_name(step.default_name)
        self.steps.append(step)
        return step

    def remove(self, step):
        """Delete a step unless another step references it; return success."""
        if any(step in other.references() for other in self.steps):
            return False
        self.steps.remove(step)
        return True

    def move(self, step, delta):
        """Shift a step up/down by `delta`, unless that would create a forward reference."""
        i = self.steps.index(step)
        j = i + delta
        if not 0 <= j < len(self.steps):
            return False
        self.steps[i], self.steps[j] = self.steps[j], self.steps[i]
        if self._forward_refs():
            self.steps[i], self.steps[j] = self.steps[j], self.steps[i]  # revert
            return False
        return True

    def rename(self, step, new):
        """Rename to `new` if it is a valid, unique Python identifier; return success."""
        if not new.isidentifier() or keyword.iskeyword(new):
            return False
        if any(other is not step and other.name == new for other in self.steps):
            return False
        step.name = new
        return True

    def step_by_name(self, name):
        """The step whose name (= its viewport structure id) is `name`, or None."""
        return next((s for s in self.steps if s.name == name), None)

    def candidates(self, step, accepts=None):
        """Ancestor steps (above `step`) eligible as a reference.

        `accepts` may be a class/tuple (isinstance test) or a predicate `step -> bool`.
        """
        ancestors = self.steps[: self.steps.index(step)]
        if accepts is None:
            return ancestors
        if isinstance(accepts, (type, tuple)):
            return [s for s in ancestors if isinstance(s, accepts)]
        return [s for s in ancestors if accepts(s)]

    def _unique_name(self, base):
        existing = {s.name for s in self.steps}
        if base not in existing:
            return base
        i = 1
        while f"{base}_{i}" in existing:
            i += 1
        return f"{base}_{i}"

    def _forward_refs(self):
        """[(step, ref), …] where a step references a non-ancestor (an invalid order)."""
        bad = []
        for i, step in enumerate(self.steps):
            ancestors = set(self.steps[:i])
            bad += [(step, ref) for ref in step.references() if ref not in ancestors]
        return bad

    # ---- build / codegen / io ----

    def prefix(self, upto=None):
        """The steps to build/show: up to *and including* `upto`, or all of them.

        `upto` is a **step** (the rollback marker), not an index, so it stays valid under
        reorder/delete; `None` — or a stale/deleted marker — means the whole list (the
        natural "show everything" default).
        """
        if upto in self.steps:
            return self.steps[: self.steps.index(upto) + 1]
        return self.steps

    def build(self, upto=None, optimize=False):
        """Best-effort build of the step prefix → context {step: cb_value}.

        Unbuildable steps (in-progress sketches, unsatisfied references) are skipped so a
        partial model still displays — the same leniency the live editor needs. `upto` bounds
        the build to the rollback marker's prefix (see `prefix`); the default builds all.
        `optimize` gates the expensive optimizer pass (off for the live viewport, on for
        write/export and the Run button); it rides on the context (see `BuildContext`).

        A step that fails is skipped but its exception is recorded in `context.errors`, so the
        failure is visible (the panel surfaces it) instead of vanishing silently.
        """
        context = BuildContext(optimize)
        for step in self.prefix(upto):
            try:
                step.build(context)
            except Exception as error:
                context.errors[step] = error
        return context

    def build_mesh(self):
        context = self.build(optimize=True)  # the real output must be optimized
        mesh = cb.Mesh()
        for step in self.steps:
            if step.adds_to_mesh and step in context:
                mesh.add(context[step])
        for step in self.steps:  # mesh-level steps (graders, …); a no-op for the rest
            step.apply_to_mesh(mesh, context)
        return mesh

    def write_blockmesh(self, path="blockMeshDict"):
        """Assemble, grade, and write the blockMeshDict. Raises if the mesh isn't valid
        (e.g. an operation missing a chop on some axis)."""
        self.build_mesh().write(path)

    def to_script(self, blockmesh_path="system/blockMeshDict"):
        lines = ["import classy_blocks as cb", "import numpy as np", expr_import_line(),
                 "", "mesh = cb.Mesh()", ""]
        for step in self.steps:
            lines += step.to_lines()
            if step.adds_to_mesh:
                lines.append(f"mesh.add({step.name})")
            lines.append("")
        lines.append(f"mesh.write({blockmesh_path!r})")
        return "\n".join(lines) + "\n"

    def save(self, path):
        with open(path, "wb") as file:
            pickle.dump(self.steps, file)

    def load(self, path):
        with open(path, "rb") as file:
            self.steps = pickle.load(file)
