# classy_polyscope — Design

A [Polyscope](https://polyscope.run/py/) front-end for
[`classy_blocks`](https://github.com/damogranlabs/classy_blocks), which generates
OpenFOAM `blockMeshDict` files. It is the sibling of the FreeCAD workbench in
`../classy_foundry`: same goal (make classy_blocks' powerful-but-cryptic scripting
API accessible through a guided, visual tool), same conceptual core, different host.

Polyscope is far more limited than FreeCAD as a GUI host — no document model, no
property system, no persistence, no CAD kernel. But it is a **mesh-native viewer**,
which is exactly what this tool needs to show. The design below leans into that:
keep classy_foundry's GUI-agnostic core, drop everything that only existed to
satisfy FreeCAD, and let classy_blocks' own geometry drive the display.

Verified baseline: `polyscope` 2.6.1 (with full `polyscope.imgui` bindings —
tables, trees, combos, input fields, drag-drop), `classy_blocks` 1.11.2,
Python 3.10.

---

## Running & environment (restart checklist)

- **Dependencies**: `pip install polyscope classy_blocks numpy` (Python 3.10). A GPU /
  GL context is needed for the live app; headless verification uses Polyscope's
  CPU-mock backend (below).
- **Run**: from inside the package dir, `python app.py`. Imports are top-level
  (`from model import …`, `from steps.… import …`, `from view.… import …`), so the
  working directory must be the package dir.
- **Artifacts** are written to the working dir: `model.pkl` (Save / Open),
  `mesh_script.py` (Export script), `blockMeshDict` (Write blockMeshDict).
- **classy_blocks local patch — not currently load-bearing.** `transform_matrix(M)` was
  added to `../classy_blocks/src` (`Point` + `ElementBase`) for an eventual transform
  gizmo. No implemented step uses it (transforms are deferred), so a stock
  `pip install classy_blocks` runs everything here. Only when the gizmo lands does this
  method need to be present (re-apply the patch, or `pip install -e ../classy_blocks`).
- **Headless tests** (no display): `ps.set_allow_headless_backends(True)` then
  `ps.init("openGL_mock")`, drive frames with `ps.frame_tick()`. Caveat learned the hard
  way: widgets behind a `CollapsingHeader`/`TreeNode` don't execute while collapsed, so
  exercise the inner draw functions (`panel._draw_steps`, `sketch_editor.draw`, …)
  *directly* in a frame, not via the top-level callback. Real mouse clicks (placement,
  picking, selection) and visual/layout correctness still need live eyes.

---

## What ports from classy_foundry, what gets rebuilt

The FreeCAD design has three layers. Only the middle one is host-independent.

| classy_foundry relied on FreeCAD for… | Polyscope offers | classy_polyscope approach |
|---|---|---|
| Document/Proxy + typed Properties (persistence) | nothing | **pickle the step list** (see below) |
| Dependency graph (InList/OutList) | nothing | plain Python references between steps; list order is already a valid codegen order |
| Auto-generated property editor | raw ImGui widgets | schema-driven panels — one `SCHEMA` per step type |
| Coin3D 3D view + element picking | structure registration + `polyscope.pick` | rebuild interaction via Polyscope picking + ray/plane math |
| `Part.*` kernel for Tier A/B preview | mesh-native viewer | **classy_blocks' own geometry** drives the display |

**Layer 2 — the classy_blocks-wrapping logic — ports essentially unchanged** (it is
host-independent), *minus* FreeCAD's `*Proxy` glue that hand-wrote `addProperty(...)`
and duplicated each constructor signature. Here that logic lives in the **step
types**: a producing step wraps a `cb` class, builds the live `cb` value, and emits
its own `to_lines()`.

**Schema-driven (decided).** Each step type declares **one** declarative `SCHEMA` — an
ordered map of `field → {kind, label, default, choices}`, where `kind` may be a scalar
(`point3`, `float`, …) or a **`ref`** to an ancestor step. A single set of registries
reads it:

- `kind → ImGui widget` renders the step's editor (no per-type UI code, no
  `if kind == ...` chains); a `ref` renders as a dropdown of eligible ancestors.
- The same schema drives `build()`, the pickled recipe fields, and `to_lines()`.

So adding a step type = declare a `SCHEMA` (+ a `build()`/`to_lines()` for its cb
mapping); the generic UI, persistence, and codegen pick it up for free. This keeps the
GUI a thin generic layer over the logic, per the DRY / no-`if` / GUI-separation
principles in `claude.md`.

---

## Document model — pickle the steps; script is one-way export

The persisted document is a **pickle of the step list**. Save = `pickle.dump` the
model; Load = `pickle.load` it back. Parsing Python source back into Python objects is
fragile and pointless when the objects can be serialized directly, so there is no
exec/round-trip load.

The classy_blocks Python script remains a **one-way export** (`to_lines()` over the
ordered steps): the portable, hand-editable/runnable artifact a user takes to produce
`blockMeshDict` or version in git. It is generated *from* the step list, never read
back into it.

What gets pickled is each step's **recipe**, not derived geometry: its scalar inputs +
references to ancestor steps (by identity). Live `cb` values and viewport structures are
rebuilt from the steps on load via a recompute — the same declarative replay used on
every edit — so the pickle stays small and version-tolerant, and we never pickle
classy_blocks' internal geometry objects.

Implication for step classes: they must pickle cleanly — restrict any
`__getstate__`/`__setstate__` to recipe fields; never persist the computed `cb` value.
(A schema-version int in the pickle guards against future field changes.)

**Units**: plain unitless numbers throughout, same as classy_foundry — dimensional
values are plain floats, no unit conversion at the classy_blocks boundary. Scale is
handled by classy_blocks' own `mesh.settings.scale`.

---

## Data model — the step list

The document is a `Model` holding one ordered `steps` list. Each **step** is a small
Python object with:

- a stable `name` — its codegen output variable and display id;
- typed **inputs** per its `SCHEMA` — scalars *and* references to ancestor steps;
- `build()` — produce or configure the live `cb` value;
- `to_lines()` — the step's statement(s).

Four build patterns, treated uniformly (full detail in **Step class hierarchy**):

- **Producing** — `name = cb.Cls(...)`: outputs a *new* `cb` value (Box, Face,
  MappedSketch, catalogue shapes, …). Args may be `ref`s or point inputs.
- **Value** — `name = <literal>`: a named literal other steps reference (Single point).
- **Configuring** — `<ref>.method(...)`: mutates an ancestor in place; output *is*
  that same value (chop, set_patch, translate, project, …).
- **Deriving** — `name = <ref>.method(...)`: a *new* value produced from an ancestor
  (copy, extract-face).

**`SCHEMA` gains a `ref` kind** — a *whole-field* reference to an ancestor step,
optionally constrained by what that ancestor produces (e.g. an `Extrude`'s profile
input accepts a Face step — or a predicate, e.g. a `Chop`'s target accepts any
operation). The schema→widget registry renders a `ref` as a dropdown of eligible
ancestors; codegen emits the referenced step's output `name`.

**Point inputs (`point` / `point_list`) are reference-or-literal *per entry*.** A point
value is either a literal `[x, y, z]` or a `Point` step (a per-entry reference) — both
resolve to coordinates. So a Face can mix referenced corners with manually-typed ones:
`profile = cb.Face([origin, [1, 0, 0], corner_b, [0, 1, 0]])`. Two small registries do
the work uniformly for every step: `RESOLVE` (value → live `cb` arg at build) and
`REF_EXTRACT` (the embedded refs, so rename-safety and the forward-ref check cover
them). This is the natural extension of the schema-driven design — adding a step type is
still "declare a `SCHEMA`."

**This supersedes the earlier "element owns a hidden chop/patch `calls` log".** A chop
is now its own visible step in the list, uniform with everything else — matching the
authoring model. (Refactor of the current `Element` + `calls` code into a step list is
pending — see Roadmap.)

**Ordering & references.** A step may reference only ancestors, so the list order is
already a valid codegen order — no separate topo-sort, just a no-forward-reference
check. `build()` replays the list to reconstruct live `cb` values; **pickle persists
the step list** (recipe only — scalars + references by identity, never `cb` geometry),
same declarative-replay property as before. See **Naming** for how references stay
rename-safe.

**The mesh.** Where `mesh.add(...)` / `set_default_patch` / `scale` / geometry live in
the step model (implicit single mesh vs. explicit mesh steps) is part of categorizing
the palette — **deferred**.

**Transforms are just a (configuring) step.** The detailed transform UI — gizmo vs.
numeric, in-place vs. derived copy/array — is **not yet settled and deliberately left
open**. `cb.ElementBase.transform_matrix(M)` was added to classy_blocks as a lossless
4×4 bridge for an eventual gizmo (additive, not yet load-bearing — revertible if no
gizmo is ever wired).

---

## Step class hierarchy (decided)

The step *types* are a proper class hierarchy: shared behaviour (build, codegen,
structure) lives in base classes, and a concrete step adds only what differs — a few
declarative class attrs plus its `SCHEMA`. No `build()`/`to_lines()` code is ever
repeated. `Box` and `MappedSketch` already demonstrate this (each ~5 declarative lines,
no logic of their own).

This is the **OO half** of the design. The *functional* code elsewhere — the
`CODEGEN`, `WIDGETS`, `RENDERERS`, and `catalog` registries — is **dispatch tables that
replace `if/elif` chains, not duplication**; every entry is unique. The rule: domain
types → inheritance; cross-cutting dispatch → data tables.

### Build-pattern base classes

Each base implements `build()` + `to_lines()` **once**, parameterised by a class attr:

| Base | Codegen shape | Declares | Palette members |
|---|---|---|---|
| `ProducingStep` *(exists)* | `name = cb.Cls(args…)` (args may be `ref`s/points) | `cb_name` | Face, MappedSketch, all Sketch-catalogue, Box/Extrude/Rotate/Loft/Wedge, all Shapes & Stacks, all Solid-catalogue |
| `ValueStep` *(exists)* | `name = <literal>` (single field is the output) | — | Single point |
| `ConfiguringStep` *(exists)* | `<ref>.method(args…)` (in-place; output = target) | `cb_method` | Translate, Rotate, Scale, Project, Set patch, Grade axis (chop), Grade edge |
| `DerivedStep` | `name = <ref>.method(args…)` (new value from an ancestor) | `cb_method` | copy, Extract face |

Two patterns get their own small base when their first member lands:

- `OptimizerStep` — `opt = cb.SketchOptimizer(target); opt.optimize()` (helper object + call).
- mesh-level config — default patch / auto-graders / scale act on the mesh, not a step.

### A concrete step is pure declaration

```python
class Cylinder(ProducingStep):
    cb_name = "Cylinder"
    category = ("Solids", "Catalogue")   # palette path (nested submenus)
    label = "Cylinder"                   # menu label
    render_kind = "operation"            # display dispatch
    SCHEMA = {...}
```

`build()`, `to_lines()`, the property panel, persistence, and display all come from the
base + registries. Adding the dozens of catalogue entries is just such declarations
plus one `catalog` line.

### Display dispatch stays DRY

A step declares a `render_kind` string (`"operation"`, `"profile"`, `"curve"`,
`"point"`, or `None`); `RENDERERS` maps that string → one renderer, so every operation
type shares one renderer — declared, not coded per type. Steps stay free of
`polyscope` (the renderer lives in `view`, keyed by the declared string), so the
one-way `view → model` rule holds.

### Gradual, not speculative

Each base is added **when its first member is implemented** (YAGNI): `ProducingStep`,
`ValueStep`, and `ConfiguringStep` exist; `DerivedStep` / `OptimizerStep` arrive with
their first type. This hierarchy is the plan the incremental work follows.

---

## Naming (decided)

Every step has a user-facing **name** that *is* its script variable, so the exported
script reads like hand-written classy_blocks (`leading_edge = cb.Face(...)`,
`channel = cb.Extrude(leading_edge, ...)`). Naming is first-class and user-driven, not
generic-with-a-number.

- **One name = the variable.** It must be a valid Python identifier and unique among
  steps. Invalid input is rejected/sanitized inline; uniqueness is enforced by a
  `model.rename(step, new)` helper (logic, not view). No separate label/Name split.
- **Default, then rename freely.** A new step gets a type-based default (`face`, then
  `face_1` on collision), shown prominently and editable on its step line. Naming is
  encouraged but **never blocks** the build.
- **Name is chrome, not `SCHEMA`.** It is the step's identity/output, handled
  uniformly by the step framework on every line — orthogonal to the per-type `SCHEMA`
  inputs. (So `SCHEMA` stays purely the typed inputs.)
- **References are by identity, not by name.** A `ref` input stores the *step object*;
  codegen resolves it to that step's *current* name. Renaming is therefore safe — it
  just changes the emitted variable everywhere, with nothing to repair (pickle
  preserves the shared object references). The name is purely a display/codegen
  attribute; identity is the link.

The name is also the Polyscope structure id and the step's display label — one string,
three uses, all satisfied by "valid identifier."

---

## Display — per-step, from each step's own geometry

Each step renders **from its own built `cb` value (or raw data)**, not from
`mesh.assemble()` — so the viewport works even while the mesh is incomplete or not
validly connected (assemble would refuse). `sync_display` builds the model once into a
context `{step: cb_value}`, wipes (`reset_selection` + `remove_all_structures`), and
renders each step via a `render_kind → renderer` registry (see **Step class hierarchy**),
then re-adds the editor's transient overlay.

Renderers (keyed by the step's declared `render_kind`):

- `"operation"` (Box, Extrude, …) — a 6-quad surface from `op.get_face(side)` for
  `side ∈ {bottom, top, left, right, front, back}`. **Those names are classy_blocks'
  patch orientations**, so a picked face maps straight to a patch side — no axis/
  orientation index to memorize (the basis for the future grade/tag-by-pick).
- `"sketch"` (MappedSketch) — a pickable point cloud + a quad surface, drawn from the
  step's *raw* positions/quads so an in-progress (unbuildable) sketch still shows.
- `"face"` (Face) — a single flat quad from `face.point_array`.
- `"point"` (Point) — a one-point cloud.
- `None` (configuring steps like Chop) — nothing.

This replaces classy_foundry's two-tier `Part.*` scheme. (The fully assembled & graded
cell mesh from `mesh.assemble()` could be an optional on-demand "show final cells" view
later, but it is not the working display.) Curved-edge preview (`op.edges` → curve
network) is a future enhancement, not yet built.

---

## Authoring model — one list of steps (decided)

This is the spine of the whole UI.

### The acceptance test

A GUI over classy_blocks is worth building **only where it is clearer than typing the
equivalent line.** classy_blocks' crypticness is **spatial and index-based** —
tracking which point is index 7, which axis is `0`, which side is `'left'`,
visualizing a rotation — **not textual**. So every affordance must remove a
*spatial/index* burden. If it doesn't, we don't build it; we just show the line.
A prettier text interface is not a win — the line was never the hard part.

### There are no UI sections — only steps

Just as a programmer writes the script in any order, the user builds in any order. The
entire document is **one ordered list of steps**, and nothing else. The earlier
Sources / References / Objects / Mesh sections are **abandoned**: they divided things
by *category*, but a flat list of steps needs no such division. Dividing the UI into
sections turned out to be both unnecessary and impossible to do cleanly — so we don't.

### A step is one statement

Each step has:

- **inputs** — its scalar parameters *plus* references to the outputs of **ancestor**
  steps (a step may reference only steps above it, exactly like a script);
- **output** — the value it produces, which later steps can reference.

A **producing** step (`face = cb.Face(...)`, `op = cb.Extrude(face, 1)`) creates a
new named output. A **configuring** step (`op.chop(0, count=10)`,
`op.set_patch('left', 'inlet')`, `op.translate([1, 0, 0])`) is *also just a step*: it
takes an ancestor as input, and its output is that same element, now configured.
**Transforms, chops, patches, graders, projections are not special cases — each is
simply a kind of step.**

### Adding steps

The user appends a new step at the bottom of the list and picks its *type* from a
palette. The one thing that needs categorizing is **that palette of step types**
(face/sketch, operation/shape, transform, grader, chop, …) — and that categorization
is **deferred**. The list itself stays uncategorized.

### Two views of the one list

- **The step list** — the script, as ordered statement-lines: each shows its type,
  the ancestors it references, and its output name; expand a line to edit scalar
  params; reorder/delete within dependency limits. Textual, transparent, the
  power-user surface. Structured statements backed by step objects — **not** parsed
  free text (so no parsing; pickle stays the document).
- **The viewport** — the spatial projection of the *selected* step: place/drag
  points, pick a face to grade or tag. This is where spatial crypticness dies.

Selection is synced between them; each leads where it is strong (spatial work in the
viewport, scalar params + structure in the step list). Both edit the one step list.
**Audience is both** (decided): newcomers build spatially, power users read/edit the
script; the two views serve them simultaneously because they are the same list.

We still **lean on Polyscope's own structure list** for show/hide/color/inspect, so
neither of our views re-implements visibility/appearance.

**UI shell (decided).** We draw our **own** ImGui window
(`set_open_imgui_window_for_user_callback(False)` + `psim.Begin("classy_polyscope")`,
default size via `SetNextWindowSize(..., FirstUseEver)`) so the panel is **resizable**
with a sensible default width. Inputs **fill the available width** (`SetNextItemWidth(-1)`
with the panel drawing the label and the widget using a hidden `##` label), so they
reflow on resize; point entries stack (combo + dropper on one line, xyz filling the line
below) to never overflow a narrow window. Point clouds render with an enlarged
`set_radius` (`POINT_RADIUS`, relative) — Polyscope's default sphere is tiny.

### Interaction primitives (all on Polyscope picking + ImGui, no scene-graph code)

- **Sketcher** (a sketch step) — *implemented*. Click places a point via
  `screen_coords_to_world_ray` ∩ work plane; nearest-point proximity snap connects quad
  corners; ImGui tables edit points/quads. ~170 lines, no Coin3D equivalent. The proof
  the platform handles the hard, spatial part.
- **Selection (viewport → list)** — *implemented*. A bare viewport click selects the
  structure; we mirror `ps.get_selection()` into `session["active"]` each frame
  (`structure_name → model.step_by_name`, `::`-suffix stripped for sketch substructures),
  synced only on change. `sync_display` calls `ps.reset_selection()` before
  `remove_all_structures()` so a stale selection can't be resolved against a replaced
  structure (the bug that threw `interpretPickResult`); the reader also guards + resets
  defensively.
- **Pick a step to fill an input (the dropper)** — *implemented for points and `ref`
  fields*. Each input shows a `pick` button (eyedropper); clicking it toggles
  `session["pick"] = (step, field, index)` and shows a "Pick mode" hint. **A bare click
  always *selects*; only the dropper arms a fill** — no ambiguity. The next viewport
  click resolves the picked structure to its step and binds it iff it is an *acceptable
  ancestor* — `picked in model.candidates(step, accepts)` (point inputs accept `Point`; a
  `ref` accepts its `accepts`), which enforces type *and* no-forward-reference. Pick mode
  pauses selection and the sketcher so the click isn't double-handled.
- **Sweep-to-3D** *(Extrude done)* — an operation step referencing a profile; pick a Face
  for `Extrude.base` via the dropper. Loft/Revolve (axis / 2nd profile) to follow.
- **Grade / tag / project** *(Grade axis done as a step)* — the spatial form is: pick a
  face → named side via `get_face` → chop / patch / projection. Same picking foundation.

---

## Step types (the palette)

There is no fixed "workflow" — the user adds steps in any order. What follows is the
*palette* of step types (the categorization of this palette is itself deferred), each
with what's cryptic about it and its spatial projection. The mesh shown is always the
real output.

| Step type | classy_blocks | Spatial projection (clarity win) |
|---|---|---|
| Point / Curve / Surface | points, curves, surfaces | place/pick points; import curve files (airfoils); load STL surfaces as pickable meshes |
| `Face` | 4 points + curved edges | pick/place corners; edge types per side |
| `MappedSketch` | positions + quads | the sketcher *(implemented)* — kept **separate** from Face (decided) |
| `Box`/`Extrude`/`Loft`/`Revolve` | sweep a profile | reference a profile step; live preview; pick points for revolve axis / 2nd loft profile |
| `Chop` (grade) | `chop(axis, …)` | *implemented* (Grade axis step); spatial form (pick face → axis) later |
| `SetPatch` (tag) | `set_patch(side, name)` | *deferred* — pick face(s) → name; `set_default_patch` not required to write |
| `Project` | `project_*(geometry)` | *deferred* — pick edge/face → pick target surface/curve |
| `Transform` | translate/rotate/scale | *UI not yet settled* (deferred) |
| Optimize | Sketch/Shape/Mesh optimizers | *deferred* |
| Write | assemble/grade/write | *implemented* — Write blockMeshDict button (no default patch needed) |

**Grading now.** An operation needs a `Chop` on each of its three axes before it
writes (verified). That's three Grade-axis steps per operation — functional but
verbose; the **Auto graders** palette items (`Auto: fixed count`, …) will later collapse
that to one step.

**Scope now.** The build→grade→write loop is closed (point/profile → sweep → grade →
blockMeshDict). Patches, projection, transforms, optimization, and the spatial grading
UI are deferred — all ride the proven `pick` foundation, so deferral costs no rework.

---

## Package layout (GUI / logic split, decided)

One-way import rule — `view → model → steps`, never the reverse — enforces the
separation mechanically:

- `classy_polyscope/steps/` — step types + their `SCHEMA`s, `build()`, `to_lines()`,
  plus `catalog.py` (the palette). Imports only `classy_blocks`; no `polyscope`.
- `classy_polyscope/model.py` — the ordered step list, reference resolution, codegen,
  pickle save/load. No `polyscope`.
- `classy_polyscope/view/` — polyscope rendering, the step-list panel + viewport
  interaction (schema→widget registry, picking). Imports `model`, never the reverse.
- `classy_polyscope/app.py` — the `ps.show()` + `userCallback` entry point.

## Roadmap

**Done.**

- **Milestone 0 — vertical slice.** `Box` (Element + SCHEMA) → `Mesh` → display from
  per-element geometry → pickle save/load → export script. Proved schema-driven
  elements, pickle-as-document, codegen (a generated script wrote a real
  `blockMeshDict`), and the GUI frame path (headless via `frame_tick`).
- **MappedSketch sketcher.** Element + display + click-to-place/snap + points/quads
  tables + delete/reindex + selection overlay. Confirmed responsive in live use —
  the platform-decision evidence.

- **Step model** — `steps` list; `ProducingStep`/`ValueStep`/`ConfiguringStep` bases;
  `ref` + `point`/`point_list` kinds; `model.rename()` (identifier + uniqueness);
  identity references; pickle + codegen over steps; forward-ref guard.
- **Step-list UI** — editable name per line, reorder/delete, **data-driven add-step
  palette** (nested popup grouped by `category`), selection-driven editor.
- **Step types** — `Point`, `Face`, `Box`, `Extrude`, `MappedSketch`, `Chop`.
- **Closed the loop** — Write blockMeshDict (verified output); script export runs standalone.
- **Literal-or-ref point inputs** — Face corners / Box points are a literal *or* a `Point`.
- **Viewport selection + dropper picking** — bare click selects a step (viewport→list);
  the `pick` dropper fills a point entry or a `ref` field (`Extrude.base`) from a clicked
  structure, accept-checked via `candidates`; stale-selection crash fixed.
- **UI shell** — own resizable window; width-filling inputs; enlarged point spheres.

**Next:**

1. **More operations** — `Loft`, `Revolve`, `Wedge`, then Shapes/Stacks (pure declarations).
2. **Extract face** — first `DerivedStep` (`name = op.get_face(side)`); pick the op + side.
3. **Auto graders** — collapse the 3-chops-per-operation into one step.
4. **Patches / projection / transforms / optimizers** — as their bases land.
5. **List → viewport highlight** — the reverse of selection (needs our own highlight,
   since Polyscope has no `set_selection`).

**Deferred (decided):** palette categorization polish, the transform UI (gizmo vs
numeric, in-place vs derived copy/array), Sources beyond curve files, non-planar
sketches.

**Step palette contents**

- References
  - Single point (fixed)
  - Points file (a list of 3d points for an interpolated curve)
  - Surface (path to an STL surface)
- Flat
  - Face (specify points manually)
  - Extract face (from an operation)
  - Mapped sketch (with an editor)
  - Sketches catalogue:
    - Quarter circle
    - Half circle
    - Circle
    - Circle (1 core)
    - Oval
    - Boxed circle
    - Splined rounds (added later)
    - Ring
- Solids
  - Simple
    - Box
    - Extrude
    - Rotate
    - Loft
    - Wedge
  - Shapes
    - Extruded shape
    - Revolved shape
    - Lofted shape
  - Stacks
  - Extruded stack
    - Revolved stack
    - Lofted stack
  - Solids catalogue:
    - Cylinder
    - Conical frustum
    - Elbow
    - Extruded ring
    - Revolved ring
    - Eighth sphere
    - Quarter sphere
    - Half sphere
    - Sphere
- Modifiers
  - copy
  - Translate
  - Revolve
  - Scale
  - Modify edge
  - Project (one or more faces)
- Optimizers
  - Sketch smoother
  - Shape smoother
  - Sketch optimizer
  - Shape optimizer
  - Mesh optimizer
- Grading
  - Grade axis
  - Grade Edge
  - Auto: fixed count
  - Auto: simple
  - Auto: inflation
- Patches
  - Set patch (one or multiple operation sides)
  - Default

---

## Resolved / proven

- **Picklability** — confirmed: recipe objects pickle/unpickle cleanly (scalars +
  references only, no live `cb` geometry); round-trip preserves values and config.
- **Re-render cadence** — rebuild on every dirty edit (`remove_all_structures` +
  re-register). Cheap and responsive in live use; no recompute button needed.
- **GUI testability** — the whole logic *and* GUI frame path run headless via
  `frame_tick`; the only thing needing live eyes is mouse-click feel (validated).

## Open questions (mostly deferred features)

- **Picking precision for chops** — Polyscope face picking gives a face index; when
  the grading/patch editor lands, confirm the index ↔ named-side mapping is stable
  across operation types (Box vs Loft vs Revolve cell ordering).
- **File dialogs / undo** — Save/Open currently use a hardcoded path; a real
  app needs a file-dialog shim and (cheap, via pickle snapshots) undo. Bounded work,
  the main "Polyscope gives no plumbing" papercut.
- **Property panel reflection** — reuse classy_foundry's per-class metadata
  (labels/enum choices) or regenerate? Mostly host-neutral.
- **Curve/surface clamps in codegen** — never emitted from `to_lines()` in
  classy_foundry; revisit when optimization/clamps come off the deferred list.
- **GUI framework — view-only escape hatch** *(deferred, not a lock-in)*. Polyscope
  can be reduced to "just the 3D view" under a different GUI framework (Qt, web) two
  ways, both supported: (1) `set_build_gui(False)` + `frame_tick()` driven from an
  external main loop; (2) headless EGL (`init('openGL3_egl')`) + render-image
  quantities / `screenshot_to_buffer`, blitted into another framework's widget. Not
  pursued: the integration is the costly part (two loops or manual mouse-coord
  re-routing — it reimplements the picking Polyscope gives for free) and it
  reintroduces the framework weight whose absence made Polyscope the choice for a
  solo dev. The designed step-list UI is well within ImGui; the real ImGui gaps
  (**file dialogs**, **undo**) are bounded and fixed in place (a dialog shim; a
  pickle-snapshot stack). Because the `view → model` split keeps `model`/`steps` free
  of `polyscope`, that layer can move under another GUI later — so this is
  revisitable, not now-or-never. Revisit only if the project pivots to a polished app
  for non-technical users, dialog-heavy workflows, or embedding in an existing tool.
