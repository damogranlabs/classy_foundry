# classy_foundry — Design

A [Polyscope](https://polyscope.run/py/) front-end for
[`classy_blocks`](https://github.com/damogranlabs/classy_blocks), which generates
OpenFOAM `blockMeshDict` files. Its goal is to make classy_blocks'
powerful-but-cryptic scripting API accessible through a guided, visual tool. This is
the **second attempt**; the first was a FreeCAD workbench (same conceptual core,
different host) — referred to below as "the FreeCAD attempt".

Polyscope is far more limited than FreeCAD as a GUI host — no document model, no
property system, no persistence, no CAD kernel. But it is a **mesh-native viewer**,
which is exactly what this tool needs to show. The design below leans into that:
keep a GUI-agnostic core, drop everything that only existed to satisfy FreeCAD, and
let classy_blocks' own geometry drive the display.

Verified baseline: `polyscope` 2.6.1 (with full `polyscope.imgui` bindings —
tables, trees, combos, input fields, drag-drop), `classy_blocks` 1.11.2,
Python 3.10.

---

## Running & environment (restart checklist)

- **Dependencies**: `pip install polyscope classy_blocks numpy` (Python 3.10). A GPU /
  GL context is needed for the live app; headless verification uses Polyscope's
  CPU-mock backend (below).
- **Run**: `python -m classy_foundry` from `src/` (entry point is
  `classy_foundry/__main__.py` → `main()` → `ps.show()`). The package uses **relative**
  imports (`from .steps … import`, `from ..model import`), so it runs as a module, not a
  loose script.
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

## What ports from the FreeCAD attempt, what gets rebuilt

The FreeCAD attempt had three layers. Only the middle one is host-independent.

| The FreeCAD attempt relied on FreeCAD for… | Polyscope offers | This tool's approach |
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

**Units**: plain unitless numbers throughout — dimensional values are plain floats, no
unit conversion at the classy_blocks boundary. Scale is handled by classy_blocks' own
`mesh.settings.scale`.

**Numeric fields are expression strings (implemented).** A scalar `float`/`int` field
stores its value as a **string** (`"pi/2"`, `"deg2rad(90)"`, `"5*2"`), not a number — so
angles/distances/counts read naturally and the exported script stays hand-written-looking
(`cb.Revolve(face, pi/2, …)`). It is evaluated in a **math-only namespace** (`eval_expr`,
a restricted `eval` over a curated set of `numpy` names — `pi`, `sin`, `deg2rad`, …) at
**build** time, and emitted **verbatim** in codegen; the exported script imports those
names (`expr_import_line()` → `from numpy import …`). A bad/mid-edit expression simply
fails to build (best-effort, so the step just drops out of the preview until it parses).
Numbers still pass through unchanged, so old pickles/defaults keep working. This is the
one place a "plain float" is deliberately a string — and it stays inside the schema-driven
path (a `kind`, a `WIDGETS` text entry, a `RESOLVE`/`CODEGEN` pair), no special-casing.

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

**`points_file` kind (implemented).** A field that holds a **file path** to a list of 3D
points; `RESOLVE` loads it with `numpy.loadtxt` at build, `CODEGEN` emits
`np.loadtxt('path')` (the script gains `import numpy as np`). Used by the **Points file**
reference curve (`cb.LinearInterpolatedCurve`). The recipe stays a tiny path — the points
re-load from the file on every build and in the exported script, so editing the file flows
through (no baked points; flag if a "freeze" option is ever wanted).

**Ordering & references.** A step may reference only ancestors, so the list order is
already a valid codegen order — no separate topo-sort, just a no-forward-reference
check. `build()` replays the list to reconstruct live `cb` values; **pickle persists
the step list** (recipe only — scalars + references by identity, never `cb` geometry),
same declarative-replay property as before. See **Naming** for how references stay
rename-safe.

**The mesh.** There is one implicit mesh. Mesh-level steps (the auto-graders, later a
mesh optimizer/smoother) act on it via the `apply_to_mesh` hook (run after every
`mesh.add`; see **Step class hierarchy**). Whether `set_default_patch` / `scale` /
geometry become explicit mesh steps or stay implicit is part of categorizing the
palette — **deferred**.

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
| `DerivedStep` *(exists)* | `name = <ref>.method(args…)` (new value from an ancestor) | `cb_method` | **Point on curve** *(done)*, copy. (Extract face turned out to fit the **face-picker** better — a `face` input + custom build — than a method-on-ref.) |
| `HelperStep` *(exists)* | `name = cb.Cls(target, args…)` then `name.<call>()` (helper object + finishing call) | `cb_name`, `cb_call` | auto-graders *(done)*, mesh/sketch/shape **smoothers** (optimizers split into producing + clamp/optimize steps — see **Optimization**) |

**`HelperStep` — the "helper object + call" family (decided).** classy_blocks' graders,
optimizers, and smoothers all share one shape: *wrap a target in a helper, then call a
finishing method* (`cb.FixedCountGrader(mesh).grade()`, `cb.SketchSmoother(s).smooth()`,
`cb.SketchOptimizer(s)…optimize()`). So they share **one** base, `HelperStep`, parameterised
by `cb_name` (helper class) + `cb_call` (the finishing method). (Optimizers are the one
exception — clamps land *between* construction and `optimize()`, so they decompose into
separate steps rather than a single helper-and-call; see the **Extra body** note below.)
Two orthogonal axes inside the family, each added with its first member (YAGNI):

- **Target = mesh vs element.** Mesh-targeted helpers (auto-graders, `MeshOptimizer`) act on
  the whole assembled mesh, so they run in the `apply_to_mesh` hook (a base **no-op**,
  overridden here), once per step *after* every `mesh.add` (`model.build_mesh`), and draw
  nothing. Element-targeted helpers (`Sketch`/`ShapeOptimizer`/`Smoother`) take a `ref`
  target and run in the normal build pass — *added when the first optimizer lands*.
- **Extra body → separate steps (revised).** Graders/smoothers are a bare `helper; call()`,
  so they fit `HelperStep` directly. Optimizers do **not**: `add_clamp` calls and the final
  `optimize()` are *separate steps* (an optimizer **producing** step, per-kind **clamp**
  configuring steps, an **optimize** configuring step). Smart points were rejected (see
  **Optimization & smoothing → Clamps are explicit steps**), so there is no `AutoOptimizer`
  and nothing extends `HelperStep` here.

**Manual chop is not in this family.** `op.chop(axis, count)` is a method on the target
in place — `ConfiguringStep`, no helper object. It stays there, unchanged.

One pattern still gets its own small base when its first member lands:

- mesh-level **config** — default patch / scale act on the mesh (also via `apply_to_mesh`).

**Marker sub-bases under `ProducingStep` (implemented).** Where a family shares attrs
*and* needs a common type for `accepts`, a thin intermediate base carries both — no
`build()`/`to_lines()` logic, just declarations:

- `SketchStep` (`render_kind="sketch_faces"`, `adds_to_mesh=False`) — the flat-sketch
  family. `DiskSketch` adds the `(centre, rim, normal)` schema the round disks share;
  `MappedSketch` also subclasses it (overriding to its own `"sketch"` raw renderer), so a
  hand-built sketch is accepted wherever the catalogue disks are.
- `ShapeStep` (`render_kind="shape"`, `adds_to_mesh=True`) — swept solids. `CatalogueShape`
  adds the round-solid submenu path. A shape's sketch input is `accepts=SketchStep`.

So a Shape accepts *any* sketch (catalogue or `MappedSketch`) by `accepts=SketchStep`, and
the marker base is the single source of that "is-a sketch/shape" truth.

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

A step declares a `render_kind` string (`"operation"`, `"sketch"`, `"sketch_faces"`,
`"shape"`, `"face"`, `"point"`, `"curve"`, or `None`); `RENDERERS` maps that string → one
renderer, so every operation type shares one renderer — declared, not coded per type.
Steps stay free of `polyscope` (the renderer lives in `view`, keyed by the declared
string), so the one-way `view → model` rule holds.

### Gradual, not speculative

Each base is added **when its first member is implemented** (YAGNI): `ProducingStep`,
`ValueStep`, `ConfiguringStep`, and `HelperStep` (its first members are the auto-graders)
exist; `DerivedStep` now exists too (first member: `OnCurvePoint`), and `HelperStep`'s element-targeted /
clamp-carrying branches with the first optimizer. This hierarchy is the plan the
incremental work follows.

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
context `{step: cb_value}`, wipes (`reset_selection` + `remove_all_structures`), draws the
**world-axes triad**, then renders each step via a `render_kind → renderer` registry (see
**Step class hierarchy**), and finally re-adds the editor's transient overlay.

A shared `_quad_mesh(point_arrays)` helper builds `(vertices, quad_faces)` from a list of
4-point arrays — reused by the operation, face, sketch-faces, and shape renderers (one quad
per array), so the quad-building lives in one place.

Renderers (keyed by the step's declared `render_kind`):

- `"operation"` (Box, Extrude, Revolve, Loft, Wedge) — a 6-quad surface from
  `op.get_face(side)` for `side ∈ {bottom, top, left, right, front, back}`. **Those names
  are classy_blocks' patch orientations**, so a picked face maps straight to a patch side —
  no axis/orientation index to memorize (the basis for the future grade/tag-by-pick).
- `"sketch"` (MappedSketch) — a pickable point cloud + a quad surface, drawn from the
  step's *raw* positions/quads so an in-progress (unbuildable) sketch still shows.
- `"sketch_faces"` (catalogue disks/oval) — the quad surface of the built sketch's
  `.faces` (each a `point_array`).
- `"shape"` (ExtrudedShape/Revolved/Lofted, Cylinder, …) — the six named sides of *each*
  operation in `shape.operations`.
- `"face"` (Face) — a single flat quad from `face.point_array`.
- `"point"` (Point) — a one-point cloud.
- `"curve"` (Points-file curve) — a polyline through `curve.discretize(CURVE_SAMPLES)` via
  `register_curve_network(name, nodes, "line")`.
- `None` (configuring steps like Chop) — nothing.

**World-axes triad (implemented).** An origin gizmo — three ambient vector quantities on an
origin point cloud, x=red/y=green/z=blue (the colour tuple *is* the unit direction) — re-added
every rebuild inside `sync_display` (not the overlay slot, which the sketcher owns). Its
structure name has a space (`"world axes"`), so it can never collide with a step name or resolve
as a selection. Polyscope has **no built-in world-axes gizmo**; this is the ~5-line
vector-quantity substitute. Its length is `0.5 · get_length_scale()`, so it tracks the **pinned**
scene (see **Scene environment** below) — legible on any model, and it no longer resizes as
geometry is added/removed.

**Block borders (implemented).** Every block surface — the sketch's quad mesh and each
operation/shape's side quads — registers with `set_edge_width(1.0)` (Polyscope's own edge-width
setting), so blocks read as bordered cells by default instead of a flat merged surface.

**Number labels — `view/labels.py` (implemented).** Polyscope has **no native text/label
quantity**, so numbers that must sit *at* a world point are drawn ourselves: `draw_labels`
projects world points to ImGui screen space via the view camera's own matrices
(`get_view_mat` + fov/aspect → the standard perspective divide; points behind the camera go NaN
and are skipped) and writes each with the **ImGui foreground draw list** (`AddText`). Because it
is camera-dependent it runs **every frame from the app callback** (like `cues`), not in the
rebuild. Its first use is the **sketch number overlay** (`sketch_editor.draw_number_labels`,
drawn only while the active step is a `MappedSketch`): the **point index** at each vertex (light
blue) and the **block index** at each quad centroid (amber) — so the points/quads tables'
index-based editing (a quad *is* four point indices) reads straight off the viewport. This is the
same projection any future world-anchored label (patch names, dimensions) would reuse.

**Scene environment — own the extents (decided).** By default Polyscope **re-fits the scene to
the data on every structure change**; since the viewport does `remove_all_structures` + re-add
on every edit, that made the length scale, ground-plane height/grid, camera scale, and triad all
lurch around — and collapse when the scene emptied. So the app **takes control**: `pin_scene()`
(at startup) calls `set_automatically_compute_scene_extents(False)`, pins a fixed default world
(`set_bounding_box` + `set_length_scale`), and sets a quiet **`shadow_only`** ground (no changing
tile grid). Nothing lurches on rebuild, and an empty scene can't collapse. `fit_view` (computes
the model's own bounds via `display.model_bounds` — the shared `geometry_of`, overlays excluded so
there's no feedback loop with the triad — then re-pins the world and reframes via
`reset_camera_to_home_view`) runs **once at startup** to frame the initial model. **Manual re-fit
uses Polyscope's own view controls** (its built-in reset/fit behaves the same on our pinned scene),
so there's no separate app button. (`geometry_of` — `render_kind → (topology, data)` — is the one
geometry table now shared by the renderers, the cue overlay, and the fit.)

This replaces the FreeCAD attempt's two-tier `Part.*` scheme. (The fully assembled & graded
cell mesh from `mesh.assemble()` could be an optional on-demand "show final cells" view
later, but it is not the working display.) Curved-edge preview (`op.edges` → curve
network) is a future enhancement, not yet built.

### Visual cues — pre/selection highlighting (`view/cues.py`, done)

The general highlighting workflow, **holding for every step type**. It is deliberately
tool-scoped, not ambient:

**No selection in normal mode (decided).** When you are not adding/editing a step, a bare
viewport click selects nothing and changes nothing — the active step (whose panel is open) is
chosen **only from the step list**. Selection — assigning an element to a tool input — happens
*only* inside a step being edited, via that input's **pick** button (viewport) or its
**dropdown** (list); the two are front-ends to one operation. This removed the old ambient
viewport→list mirror *and* the `last_selection` pre-seed hack (both existed only to reconcile an
ambient selection with picking, which no longer coexist — a net simplification; `selection.py`
is gone).

**Cues are sourced from the active step, per frame.** `cues.update_cues` derives a set of
`(element, role)` and draws each as a **reserved-name overlay structure** (`"cue N"` — a space
=> never a step name / selection, like `"world axes"`), *after* `sync_display` so the cues
survive its `remove_all_structures`. An *element* is a `Step` (its whole output), a `FaceRef`
(one face), or a literal `("point", [x,y,z])`; geometry comes from the cached build context
(`session["context"]`, the `{step: cb_value}` map `sync_display` now returns) and reuses
`display`'s primitives (`element_quads`, `_quad_mesh`, `POINT_RADIUS`). Four roles, by colour:

- **output** (calm blue) — the active step's own produced geometry, so you see what you edit;
- **input** (green) — *every* ancestor element the active step references (what it consumes);
- **focus** (orange) — the one input whose pick is currently armed, drawn stronger.

**Hover *preselection* was tried and dropped (decided).** A per-frame `ps.pick` at the cursor
(viewport, while armed) plus dropdown-entry hover fed a pale-yellow candidate cue. In live use it
*flickered* and *blocked the committing click*, and the static highlighting above already reads
clearly — so it was reverted entirely (no `hover_preselect`, no `session["preselect"]`). The
framework still accommodates it cheaply if ever revisited.

Dispatch is table-driven throughout (no `if`-chains, mirroring `display.RENDERERS`): `render_kind
→ geometry` (`GEOMETRY`), `element type → geometry` (`ELEMENTS`), schema `kind → field elements`
(`FIELD_ELEMENTS`), `topology → register` (`RENDER`). A **single face/point** renders as a filled
glow (lifted toward the camera so it neither z-fights nor is occluded); a **whole solid** renders
as a wireframe outline, so many simultaneous highlights stay legible. Colours/sizes are tunable
constants. **Edges** get a `GEOMETRY` entry when edge geometry actually renders (`op.edges`,
deferred).

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

### Rollback marker — build up to the editing step (decided)

Borrowed wholesale from parametric CAD's feature-tree rollback bar. The viewport shows
geometry built **only up to the currently-marked step**; everything after the marker is not
built and not drawn. One mechanism that pays for many:

- **Undo / reset / snapshot dissolve.** "Undo the optimization" = put the marker before the
  optimize step; the un-optimized state rebuilds from the untouched upstream definition. No
  snapshot stack, no reset button, no stale-tracking.
- **Clutter and scope.** Downstream geometry can't be needed by upstream work (the reference
  DAG only points backward), so hiding it loses nothing relevant and de-clutters the viewport
  and picking.
- **In-place mutation is harmless.** Each render re-executes the step prefix fresh, so a step
  that mutates in place (an optimizer) only ever touches the freshly-built copy of *this*
  render — the prefix rebuild *is* the working copy.
- **"Show everything" is just the marker fully advanced** — the normal full-model view is the
  special case, not a separate mode.

The marker sits on **any** step uniformly — "a step is a step", no per-type behaviour.

**Selecting a step *is* rolling the marker (unified, revised).** The earlier design kept two
independent cursors — `session["active"]` (which step's panel is open) and the marker (how far
the model builds) — moved by separate gestures (a casual list-click set only `active`; a per-row
`(o)`/`( )` toggle or an **Edit** button moved the marker). That split three controls across the
row (rollback toggle, type button, Edit) for one intent: *work on this step*. So they were
**merged** — a step's row button now sets **both** `active` and `marker`, always editing
in-context (downstream suspended, exactly like CAD), and the separate rollback toggle and Edit
button are gone. Only two per-row controls remain (plus delete): the `::` reorder handle and the
step button. This can't cause the thing "kept separate" guarded against (a stray rebuild from
*inspecting*), because ambient viewport selection was already removed (see **Visual cues**) —
nothing moves the active step except a deliberate list-click. Adding a step clears the marker to
show-all so the new step is visible; "show everything" is otherwise just selecting the last step.

This changes the rebuild cadence (**Resolved/proven**): `sync_display` builds the **prefix up
to the marker**, not the whole list.

### Interaction primitives (all on Polyscope picking + ImGui, no scene-graph code)

- **Sketcher** (a sketch step) — *implemented*. Click places a point via
  `screen_coords_to_world_ray` ∩ work plane; quad corners are selected by `ps.pick` world
  position (depth-correct, so off-plane on-curve points select correctly — *not* work-plane
  proximity); ImGui tables edit points/quads. ~170 lines, no Coin3D equivalent. The proof
  the platform handles the hard, spatial part.
  - **Reference-point reuse** *(implemented)* — in point mode a click that lands on a
    reference point (`PointStep` — Single point / on-curve) **snapshots its exact position**
    into the sketch (pick-based, via `ps.pick` → step → built value); a click that misses
    drops a free point on the work plane. Snapshot, *not* a live ref: the sketch stays a
    plain position list so it transforms rigidly — the curve binding lives in the clamp, not
    the sketch (the resolution of the transform problem). This is what lets a sketch vertex
    sit exactly on an on-curve point so the optimizer can clamp it.
- **Selection is tool-scoped, not ambient (decided; the old viewport→list mirror is removed).**
  A bare viewport click in normal mode selects nothing; `session["active"]` is set **only from
  the step list**. There is no `sync_selection`/`session["select"]`/`last_selection` machinery
  anymore — highlighting is driven from the active step by `cues` (see **Visual cues**), and
  assigning an element to an input is the dropper/dropdown (below). `sync_display` still calls
  `ps.reset_selection()` before `remove_all_structures()` (belt-and-braces: keeps Polyscope's
  own click-selection from lingering across a rebuild).
- **Pick a step to fill an input (the dropper)** — *implemented for points and `ref`
  fields*. Each input shows a `pick` button (eyedropper); clicking it toggles
  `session["pick"] = (step, field, index)` and shows a "Pick mode" hint. **A bare click
  always *selects*; only the dropper arms a fill** — no ambiguity. The next viewport
  click resolves the picked structure to its step and binds it iff it is an *acceptable
  ancestor* — `picked in model.candidates(step, accepts)` (point inputs accept `Point`; a
  `ref` accepts its `accepts`), which enforces type *and* no-forward-reference. Pick mode
  pauses the sketcher so the click isn't double-handled. `picker._resolve` turns a `PickResult`
  into the bound element (a `FaceRef` for a `face`/`face_list` field, else the picked step) or
  `None`; `handle_pick` → `_bind` stores it.
  - **No steal-the-selection problem anymore.** With ambient selection removed, the dropper no
    longer competes with a viewport→list mirror, so the old `last_selection` pre-seed is gone
    (Polyscope's own click-selection is simply ignored, and reset on the next rebuild).
- **Sweep-to-3D** *(Extrude, Revolve, Loft, Wedge done)* — an operation step referencing a
  profile; pick a Face for `Extrude.base`/`Loft`/`Revolve`/`Wedge` via the dropper. Revolve
  axis is a literal `point3`; origin is a reference-or-literal point. The Shape family
  (Extruded/Revolved/Lofted) sweeps a **sketch** the same way.
- **Grade / tag / project** *(Grade axis done as a step)* — the spatial form is: pick a
  face → named side via `get_face` → chop / patch / projection. Same picking foundation.
- **Drag-reorder** *(implemented)* — a per-row `::` grab handle replaces the up/down buttons;
  holding it and dragging drives `model.move(step, ±1)` one swap per row-pitch crossed (the
  classic ImGui swap-on-cross idiom: `IsItemActive` + `GetMouseDragDelta`). A move blocked by
  the no-forward-reference guard simply doesn't reset the delta, so the drag *sticks* at the
  dependency wall — the guard rendered as **felt resistance**, no extra code.
- **Rollback marker** *(implemented; no longer a separate control)* — selecting a step (its row
  button) rolls `session["marker"]` (a *step*, not an index) to that step, so the viewport builds
  the prefix up to the step you're editing (`model.prefix` / `sync_display(upto=…)`), rows past it
  greyed. There is no per-row `(o)`/`( )` toggle and no separate Edit button — one gesture
  selects, edits, and rolls the marker (see **Rollback marker** above). Adding a step clears the
  marker back to show-all.

---

## Step types (the palette)

There is no fixed "workflow" — the user adds steps in any order. What follows is the
*palette* of step types (the categorization of this palette is itself deferred), each
with what's cryptic about it and its spatial projection. The mesh shown is always the
real output.

| Step type | classy_blocks | Spatial projection (clarity win) |
|---|---|---|
| Point *(done)* / Curve *(done)* / Surface *(STL load+show done)* | points, curves, surfaces | place/pick points; **Points-file curve** *(implemented — `LinearInterpolatedCurve` from a file)*; **STL surface** *(implemented — load via trimesh, shown muted as a reference backdrop; reference-only, **projection** wires the path into codegen later)* |
| `Face` *(done)* | 4 points + curved edges | pick/place corners; edge types per side *(edges deferred)* |
| `ExtractFace` *(done)* | `op.get_face(side)` | **click a face** on any operation/shape → a reusable profile (a `FaceStep`, so Extrude/Loft accept it). Uses the patch face-picker (a single `face` input), not the ancestor's `get_closest_face(point)` — exact, click-the-face |
| `Connector` *(done)* | `cb.Loft(faceA, faceB)` | **click two faces** → the bridging block, in one step (fast intermediate geometry). Two `face` inputs |
| `MappedSketch` *(done)* | positions + quads | the sketcher *(implemented)* — kept **separate** from Face (decided); now a `SketchStep` so it feeds Shapes |
| Sketch catalogue *(done)* | Disk/Oval/… sketches | declared from points; `"sketch_faces"` render |
| `Box`/`Extrude`/`Loft`/`Revolve`/`Wedge` *(done)* | sweep a profile | reference a profile step; live preview; pick points for revolve axis / 2nd loft profile |
| Shapes & catalogue solids *(done)* | sweep a sketch / ready-made solids | Extruded/Revolved/Lofted shape (sketch ref); Cylinder/Frustum/Elbow/rings/spheres (points). Grade with an **auto-grader** (no per-shape chopping — see below). |
| `Chop` (grade) | `chop(axis, …)` | *implemented* (Grade axis step, **operations only**); spatial form (pick face → axis) later |
| Auto-graders *(done)* | `FixedCount`/`Simple`/`Inflation` grader | a `HelperStep`: `cb.Grader(mesh, …).grade()`; grades every ungraded row → the one thing a Shape needs to write |
| `SetPatch` (tag) *(done)* | `op.set_patch(side, name)` per picked face | **click faces → name**: a patch is a name + a set of picked faces; the system derives each operation + side (see **Patches** below). Works on operations *and* shapes uniformly. `set_default_patch` not required to write |
| `Project` | `project_*(geometry)` | *deferred* — pick edge/face → pick target surface/curve |
| `Transform` *(translate/rotate/scale/copy done)* | `op.translate/rotate/scale(…)`, `op.copy()` | plain `ConfiguringStep`s on cb's uniform element protocol (operations/shapes/sketches/faces). **Numeric** (the "gizmo vs numeric" UI question sidestepped — numeric first); `origin` is a pickable `point` pivot (default world origin, not cb's centroid). `Copy` is a `DerivedStep` (new element, `render_kind="element"` → unified renderer); copies are first-class targets (transform/patch/connect a copy). Patterned multi-copy (**arrays**) is left to **Stacks**, not a standalone step |
| Smooth / Optimize | Sketch/Shape/Mesh smoothers & optimizers | smoothers are `HelperStep`s; optimizers decompose into producing + per-kind **clamp steps** + optimize, on cb's existing clamp API (see **Optimization & smoothing**) |
| Write | assemble/grade/write | *implemented* — Write blockMeshDict button (no default patch needed) |

**Grading model (decided).** classy_blocks shapes *can* be chopped per-axis, but that means
per-shape recipes (and `chop_axial/radial/tangential` quirks — spheres have no generic
`chop` at all). We **don't grade shapes manually**. Instead: the operation `Chop` (single
block, done) handles the specific axes a user cares about, and an **auto-grader** fills in
everything else. A grader grades only rows still ungraded (`row.count == 0`), so a manual
`Chop` and a grader compose. This is what unblocks every Shape / catalogue solid from
writing a blockMeshDict — *without* any shape-specific chop code.

**Patches (decided, done).** classy_blocks' per-shape patch shortcuts (`set_outer_patch`,
`set_symmetry_patch`, …) differ shape to shape — `if`-ing to each is exactly what we avoid.
Instead a patch is **a name plus a set of clicked faces**, and the system derives the
operation + side of each. This is uniform across bare operations *and* shapes/stacks: the
viewport renders an operation as six side quads and a shape as `len(operations) × 6`, so a
picked face index alone gives both the operation (`operations_of(value)[index // 6]`, where
`operations_of = getattr(value, "operations", [value])` — a shape exposes `.operations`, a
bare op *is* its operation) and the side (`SIDES[index % 6]`). A `FaceRef(step, index)`
stores only that (a step reference + an int, so it pickles), resolving lazily at build
(`op.set_patch(side, name)`) and codegen. The picker gains an *accumulating* `face_list`
mode (each click appends, stays armed). No per-shape code, no second dropdown — the same
flat-index idea generalizes to the planned spatial Chop (pick face → axis).

**Scope now.** The build→grade→write loop is closed (point/profile → sweep → grade →
**patch** → blockMeshDict), so a runnable case comes out. Projection, transforms, and the
spatial grading UI are deferred — all ride the proven `pick` foundation, so deferral costs
no rework.

---

## Optimization & smoothing

Both split sharply by cost. **Optimizers are implemented** (the producing + clamp + optimize
steps below — `SketchOptimizer` only so far; Shape/Mesh deferred), built on cb's existing
clamp API after smart points were rejected (see **Clamps are explicit steps**). **Smoothers
are still planned** — they're plain `HelperStep`s (`helper = cb.Cls(target); helper.<call>()`).

### Smoothers — cheap, inline (build next)

`MeshSmoother` / `SketchSmoother` are instant and clamp-free, so they're plain
`HelperStep`s with `cb_call="smooth"` that run on **every build** like any other step:

- `MeshSmoother` is **mesh-targeted** — runs in `apply_to_mesh`, exactly like a grader.
- `SketchSmoother` is the **first element-targeted** `HelperStep` — its target is a sketch
  `ref`, and it mutates that sketch *in place during the build pass*, before any dependent
  sweep builds. Each rebuild constructs a fresh sketch and smooths it once, so there is no
  compounding.

These are the warm-up that proves the element-target branch; no button, no special-casing.

### Optimizers — expensive, decoupled from the live rebuild *(implemented)*

An optimizer can take a while, and it **mutates its target mid-pipeline** (a sketch/shape
the downstream sweep depends on). Running it inside the every-dirty-edit rebuild would
freeze the UI, so it is kept off that path and runs in exactly two places:

- a **Run button** on the optimizer step — on demand, for preview;
- at **write / export** — the real output must be optimized; slowness is acceptable there.

So `build()` gains an `optimize` flag: `build(optimize=False)` for the live viewport
(optimizers construct but **skip** `optimize()`), `build(optimize=True)` for
`build_mesh`/write. Element optimizers run inline in build order (before their dependents,
since mutation is in place); a mesh optimizer runs in `apply_to_mesh` like a grader.
**Codegen always emits `optimize()`** — never baked coordinates; the exported script
recomputes faithfully, and only the GUI preview skips it.

**In-place mutation is contained by the rebuild; undo is the marker.** Every rebuild
reconstructs the prefix from source (the optimize step mutates a freshly-built target, never
a persisted one), so re-running never compounds and pressing Run twice is idempotent. And
"undo the optimization" needs no snapshot: it is just moving the **rollback marker** (see
**Authoring model → Rollback marker**) before the optimize step — the upstream definition was
never touched, so the un-optimized state simply rebuilds.

**Postponed for v1 (decided):** result **caching** (after Run, the optimized preview shows
until the next dirty edit, then reverts — the real geometry still comes out at write) and a
shared **output/console window** for the optimizer report. Both deferred; the console will
later serve write/build errors too.

### Clamps are explicit steps — no smart points (decided, reversed)

A clamp pins a mesh vertex and says how it may move (free / on-line / on-plane / on-circle /
on-curve / fixed). classy_blocks' optimizer grid is deliberately **coordinate-addressed**: a
`CurveClamp(position, curve, param)` is matched back to its vertex *by coordinate within
`TOL`* (`grid.py`), junctions are bare indices with no link to a construct point. **That
coordinate-addressing is the whole mechanism we lean on** — a clicked point's position *is*
its identity; nothing more is needed to name the vertex a clamp acts on.

**Smart points were explored and rejected.** The earlier plan had classy_blocks grow *smart
points* (a point carrying its own constraint) + an `AutoOptimizer` that reads them. Pursuing
it meant pulling surfaces / `trimesh` into the geometry primitives and overhauling cb's point
types to solve what is a **GUI** problem — solving one problem by creating three. (Note: the
objection was to trimesh *inside cb's primitives*; trimesh as a foundry-side dependency for
loading reference STLs to display is a separate, accepted call.) The
blinking-red-light test failed, so **classy_blocks is left untouched** and the feature is
built entirely on the foundry side, against cb's existing coordinate-addressed clamp API.

**Constraints are steps; points stay plain.** A point placed on a curve uses the curve only
as construction geometry for placement; it does not carry a live constraint. *Movement during
optimization is decided entirely by clamp steps*, and the default is that every vertex is
**fixed** (no clamp). "Releasing" a vertex = adding a clamp step. So three step kinds, all in
the existing taxonomy — no new machinery (**all implemented** in `steps/optimize.py`):

- **Optimizer step** (`OptimizerStep` / `SketchOptimizer`) — produces `cb.SketchOptimizer(target)`
  (a target `ref`); `render_kind=None` (the target it optimizes already shows). Its output is
  the optimizer object later steps reference. `Shape`/`Mesh` variants deferred.
- **Clamp steps** (`ClampStep` + one subclass per kind: Free/Line/Plane/Radial/Curve) — each a
  `ConfiguringStep` on the optimizer: `optimizer.add_clamp(cb.CurveClamp(position, curve, …))`.
  One step type per clamp class, so dispatch is the step framework's job — no `if`-ladder. A
  clamp step references `(optimizer, point, geometry)`; the **point is a `point` input named by
  the existing dropper** (`handle_pick` fills it from a clicked structure, accept-checked via
  `candidates`) — the "pick-snap" we'd sketched already exists, so clamp authoring adds *no*
  picking code. Codegen resolves the point ref to its position, which cb matches to the vertex
  by coordinate.
- **Optimize step** (`Optimize`) — `optimizer.optimize(max_iterations=…)`; the expensive call
  (see below), gated by the `build(optimize=…)` flag and a **Run** button (`_optimize_editor`
  → `session["run_optimize"]` → one-shot `build(optimize=True)`). `max_iterations` is a plain
  schema field — fast-but-rough during authoring, raised before export.

Default-fixed means coincident/degenerate points need no guarding: cb's optimizer already
refuses degenerate cells and the user sees the problem in the viewport — validation lives in
perception + the downstream, not in defensive code.

(The on-surface clamp case still waits on cb surface support — `ParametricSurfaceClamp` is
function-based — so clamping *to* a loaded STL is deferred even though STL load+display now
exists. On-line/on-plane/on-curve need nothing new.)

---

## Package layout (GUI / logic split, decided)

One-way import rule — `view → model → steps`, never the reverse — enforces the
separation mechanically:

- `classy_foundry/steps/` — step types + their `SCHEMA`s, `build()`, `to_lines()`,
  plus `catalog.py` (the palette). Imports only `classy_blocks`; no `polyscope`.
- `classy_foundry/model.py` — the ordered step list, reference resolution, codegen,
  pickle save/load. No `polyscope`.
- `classy_foundry/view/` — polyscope rendering, the step-list panel + viewport
  interaction (schema→widget registry, picking). Imports `model`, never the reverse.
- `classy_foundry/__main__.py` — the `ps.show()` + `userCallback` entry point.

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
- **Step types** — `Point`, `Face`, `Box`, `Extrude`, `MappedSketch`, `Chop` (and all the
  operations/sketches/shapes/curve listed below).
- **Closed the loop** — Write blockMeshDict (verified output); script export runs standalone.
- **Literal-or-ref point inputs** — Face corners / Box points are a literal *or* a `Point`.
- **Viewport selection + dropper picking** — bare click selects a step (viewport→list);
  the `pick` dropper fills a point entry or a `ref` field (`Extrude.base`) from a clicked
  structure, accept-checked via `candidates`; stale-selection crash fixed; **pick no longer
  steals the edited selection** (the `last_selection` pre-seed + transient-empty handling).
- **UI shell** — own resizable window; width-filling inputs; enlarged point spheres.
- **Palette order** — follows `CATALOG` insertion order, not alphabetical (the `sorted()`
  in the menu was removed; `CATALOG` is grouped + ordered to match this doc's palette).
- **World-axes triad** — origin gizmo (x/y/z = red/green/blue ambient vectors), sized to the
  pinned scene so it stays legible and stops resizing.
- **Scene environment** — own the extents: `pin_scene` disables Polyscope's per-rebuild auto-fit
  (fixed world + `shadow_only` ground, no more lurching/collapsing); `fit_view` (`model_bounds`)
  frames the model **once at startup**, and manual re-fit uses Polyscope's own view controls.
  `geometry_of` is the shared `render_kind → geometry` table (renderers + cues + fit).
- **More operations** — `Revolve`, `Loft`, `Wedge` (pure `ProducingStep` declarations,
  all `"operation"` render).
- **Expression inputs** — `float`/`int` fields are math-expression strings (`pi/2`,
  `deg2rad(90)`), eval'd at build, emitted verbatim; `eval_expr` + `expr_import_line`.
- **Sketch catalogue (Flat)** — `Circle`/`Circle (1 core)`/`Half circle`/`Boxed circle`/
  `Oval` on `SketchStep`/`DiskSketch`; `"sketch_faces"` renderer; `MappedSketch` rebased
  onto `SketchStep` so it feeds Shapes.
- **Shapes (Solids → Shapes)** — `ExtrudedShape`/`RevolvedShape`/`LoftedShape`, sweeping
  any `SketchStep`; `"shape"` renderer over `shape.operations`.
- **Catalogue solids (Solids → Catalogue)** — `Cylinder`, `Frustum`, `Elbow`,
  `ExtrudedRing`, `RevolvedRing` (Face cross-section), `EighthSphere`/`QuarterSphere`/
  `HalfSphere` (`Hemisphere`). Optional trailing cb args omitted → defaults.
- **Points-file reference curve (References)** — `PointsFileCurve`
  (`cb.LinearInterpolatedCurve`) via the new `points_file` kind; `"curve"` renderer.
- **Auto-graders (Grading → Automatic)** — `FixedCount`/`Simple`/`Inflation` on the new
  `HelperStep` base (`cb.Grader(mesh, …).grade()`, via the `apply_to_mesh` hook); a `choice`
  field kind (combo) for `Simple.take`. **This is what lets Shapes / catalogue solids write
  a blockMeshDict** — grading is a grader + optional manual operation `Chop`, with *no*
  per-shape chop code. (Supersedes the earlier "shape grading" plan.)

**Next:**

1. **Stacks** — `Extruded/Revolved/Lofted stack` (the remaining shape family).
2. **Extract face** *(done)* — `ExtractFace`: click a face → `op.get_face(side)` as a reusable
   profile, on a shared `FaceStep` base (Extrude/Loft `accept` it). Reuses the patch
   face-picker via a single `face` input — see **Patches** / `steps/faces.py`.
   **Connector** *(done)* — `cb.Loft(faceA, faceB)`: click two faces → the bridging block in
   one step (fast intermediate geometry).
3. **Smoothers** — `MeshSmoother` (mesh-targeted, like a grader) + `SketchSmoother` (first
   element-targeted `HelperStep`). Cheap, run inline, no clamps. See **Optimization &
   smoothing**.
4. **Rollback marker + drag-reorder** *(implemented; live drag-feel pending eyes)* —
   `sync_display`/`model.build`/`model.prefix` build the **prefix up to the marker** (a step
   ref, `None`=all); a `::` drag-reorder handle replaces the up/down buttons. The rollback toggle
   and separate Edit button were **removed** — selecting a step's row button now rolls the marker
   to it (active *and* marker in one gesture; adding a step clears to show-all). See
   **Authoring model → Rollback marker**.
5. **Optimizers** *(implemented — `SketchOptimizer` only; Shape/Mesh deferred)* — built on
   cb's existing coordinate-addressed clamp API (smart points rejected). `OptimizerStep` +
   per-kind **clamp steps** (Free/Line/Plane/Radial/Curve; point named via the existing
   dropper) + an `Optimize` step (Run button, `max_iterations` field, `build(optimize=…)`).
   See **Optimization & smoothing → Clamps are explicit steps**.
6. **Patches** *(done)* — `SetPatch`: click faces → name, uniform over operations and shapes
   via the flat face-index → (operation, side) mapping; accumulating `face_list` pick +
   `FaceRef`. See **Patches (decided, done)**.
7. **STL surface reference** *(done)* — `Surface`: load via trimesh, show muted as a backdrop;
   reference-only (projection wires the path into codegen later). See the step table.
8. **Transforms** *(translate/rotate/scale/copy done)* — `Translate`/`Rotate`/`Scale`
   (`ConfiguringStep`s) + `Copy` (`DerivedStep` → new element, unified `"element"` renderer),
   on cb's uniform element protocol; numeric, pickable-point pivot. Patterned multi-copy
   (linear/polar **arrays**) is **left to Stacks** (cb's own multi-element family — see below),
   not a standalone array step. See the `Transform` table row.
9. **Edges / projections** — to discuss; the Points-file curve is the foundation (edges on
   faces, projection targets).
10. **List → viewport highlight** — *done as part of **Visual cues***. Selecting a step in the
    list highlights its output (calm-blue outline) and every input it references (green) in the
    viewport; `view/cues.py` sources all highlights from the active step. (Polyscope has no
    `set_selection`, so this is our own overlay, not its selection.)

**Deferred (decided):** palette categorization polish, the transform **gizmo** (numeric
translate/rotate/scale/copy done; patterned multi-copy is left to **Stacks**, not a standalone
array step), projection onto STL surfaces (load+show done), non-planar sketches, a file-dialog
picker for `points_file` (path is plain text for now). A standalone `Vector` reference was
tried and **reverted** (an arrow-rendered point) — a proper `Axis` belongs in classy_blocks
core; reference-point + literal axis covers the vast majority. `QuarterDisk`/`Annulus`/full
`Sphere` are absent only because classy_blocks doesn't export them at top level (one-line cb
export to add).

**Axis cue (implemented).** A cosmetic overlay, *not* a new reference type: a step declares
`AXIS = (origin_field, direction_field)` (a base `Step` class attr, default `None`) and its
active-step cue then draws that axis as a **point-and-vector arrow** — the origin (resolved via
the build's `resolve_value`, so a literal or a `Point` ref both work) plus the `point3` direction,
rendered with the **same** scene-scaled ambient vector-quantity the world triad uses
(`display.axis_vectors`, shared). It rides the existing cue machinery (an `("axis", step)` element,
a `RENDER["axis"]` entry, magenta), so it clears/scales like any other highlight. Declared on
`Revolve` and `Rotate`; any origin+direction step opts in with one line.

**Step palette contents** (✓ = implemented)

- References
  - ✓ Single point (fixed)
  - ✓ Point on curve (a curve + parameter → `curve.get_point(param)`; referenceable like any point)
  - ✓ Points file (a list of 3d points → `LinearInterpolatedCurve`)
  - ✓ STL surface (load via trimesh, shown as a muted reference backdrop)
- Flat
  - ✓ Face (specify points manually)
  - ✓ Extract face (click a face on an operation/shape)
  - ✓ Mapped sketch (with an editor)
  - Sketches catalogue:
    - Quarter circle *(absent — `QuarterDisk` not cb-exported)*
    - ✓ Half circle
    - ✓ Circle
    - ✓ Circle (1 core)
    - ✓ Oval
    - ✓ Boxed circle
    - Splined rounds (added later)
    - Ring *(absent — `Annulus` not cb-exported)*
- Solids
  - Simple
    - ✓ Box
    - ✓ Extrude
    - ✓ Rotate *(= `Revolve` operation)*
    - ✓ Loft
    - ✓ Connector *(loft between two clicked faces)*
    - ✓ Wedge
  - Shapes
    - ✓ Extruded shape
    - ✓ Revolved shape
    - ✓ Lofted shape
  - Stacks
  - Extruded stack
    - Revolved stack
    - Lofted stack
  - Solids catalogue *(`("Solids", "Catalogue")`)*:
    - ✓ Cylinder
    - ✓ Conical frustum
    - ✓ Elbow
    - ✓ Extruded ring
    - ✓ Revolved ring
    - ✓ Eighth sphere
    - ✓ Quarter sphere
    - ✓ Half sphere *(`Hemisphere`)*
    - Sphere *(absent — full `Sphere` not cb-exported)*
- Modifiers
  - ✓ Copy *(`element.copy()` → new solid; one renderer covers op/shape copies)*
  - ✓ Translate
  - ✓ Rotate *(cb `rotate`; pivot `origin` is a pickable point)*
  - ✓ Scale
  - Modify edge
    - Arc (midpoint)
    - Arc (origin)
    - Arc (angle and axis)
    - Project (duplicated in project)
    - On Curve
  - Project:
    - Point
    - Edge (duplicated in modify edge)
    - Face
- Optimizers
  - Sketch smoother
  - Shape smoother
  - Sketch optimizer
  - Shape optimizer
  - Mesh optimizer
- Grading
  - ✓ Grade axis *(operations only — shapes grade via an auto-grader, by design)*
  - Grade Edge
  - Automatic:
    - ✓ Fixed count
    - ✓ Simple
    - ✓ Inflation
- Patches
  - ✓ Set patch (click faces → name; operations and shapes)
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
