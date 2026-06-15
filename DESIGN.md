# classy_foundry — Design Notes

A FreeCAD workbench that serves as a GUI for `classy_blocks`
(https://github.com/damogranlabs/classy_blocks), which generates OpenFOAM
`blockMeshDict` files. classy_blocks is powerful but its text/scripting-only
interface is cryptic for most users; this project aims to make its capabilities
accessible through a guided, visual FreeCAD workbench.

> Naming note: this project was initially sketched under the working name
> "classy_mason". It has been renamed to **classy_foundry**. The current
> `freecad/classy_mason/` directory and `pyproject.toml` (`name = "classy_mason"`)
> are unrelated FreeCAD-tutorial boilerplate and need renaming to `classy_foundry`
> as a future cleanup step.

## Three-layer architecture

1. **Layer 1 — Backend (`classy_blocks`)**: imported as-is, in its own repo.
   No changes made *specifically* to serve the GUI. Bugfixes/refactors are welcome,
   but existing hand-written scripts must keep working identically.
2. **Layer 2 — Handling layer**: translates between FreeCAD entities (Document
   Objects defined by classy_foundry) and a finished, idiomatic classy_blocks
   Python script.
3. **Layer 3 — GUI**: the FreeCAD workbench itself — what the user sees, how it
   guides mesh creation, and how the in-progress mesh is displayed.

Design proceeds in roughly this order: Layer 1 prerequisite refactor → Layer 2 →
Layer 3, though Layer 3's needs (chop/patch editing, tiers, preview) inform Layer 2's
data model.

---

## Layer 1 — classy_blocks: pending unification (separate repo/effort)

The codebase already shows the seeds of a unification between the "single" and
"collection" hierarchies:

- `construct/operations/loft.py:6` — `Loft = Operation` (literal alias already).
- `construct/operations/extrude.py` (`Extrude(Loft)`, takes a `Face`, does
  `top_face = base.copy().translate(...)`, `super().__init__(base, top_face)`)
  is structurally identical to `construct/shape.py`'s `ExtrudedShape(LoftedShape)`
  (takes a `Sketch`, does `top_sketch = bottom_sketch.copy().translate(...)`,
  `super().__init__(bottom_sketch, top_sketch)`, which builds one `Loft` per
  `(i,j)` in `sketch_1.grid`).
- Same pairing for `Revolve`/`RevolvedShape` (rotate + add `Angle` side edges,
  the latter just iterating `self.operations`).
- `construct/shape.py:119` already has `# TODO: make operations universal - work
  on faces or sketches equally`.

**Conceptually**: `Face` is "a `Sketch` whose `grid` is `[[self]]`" (with
`chops = [[0],[0]]`), and `Operation` is "a `Shape` whose `grid` is `[[self]]`".
If `Face`/`Sketch` and `Operation`/`Shape` are unified along these lines,
`Extrude`/`Revolve`/`Wedge`/`Loft` etc. each become **one** class operating on a
grid of 1-or-many, instead of two near-duplicate classes (one for "Face → single
block", one for "Sketch → multiple blocks").

**Constraints**:
- Must remain backward compatible — all existing scripts using `cb.Face`,
  `cb.Operation`, `cb.Box`, `cb.Sketch`-derived shapes etc. must continue to behave
  identically.
- This is its own effort with its own test/PR cycle in the `classy_blocks` repo,
  independent of the GUI's value to classy_blocks generally.

**Why it matters for the GUI**: today, a GUI object model would need *four*
families — Face, Sketch, Operation, Shape — each with their own property panels,
chop/patch logic, etc. After unification, the GUI only needs **two** — a
"2D profile" type (Face/Sketch unified) and a "3D operation" type
(Operation/Shape unified) — and Sketch→Shape support becomes "the same Document
Object type, now also accepting an N-face input" rather than a parallel object
model.

**Sequencing**: classy_foundry's v1 scope (Face → Operation → Mesh, see below) is
the single-element special case of the unified model either way, so it is
unaffected by whether this refactor has landed. Sketch→Shape GUI support should be
*deferred until after* this unification lands in classy_blocks.

---

## Layer 2 — Handling layer (FreeCAD entities ↔ classy_blocks script)

**Output target**: a generated, idiomatic Python script using plain
`classy_blocks` calls (e.g. `import classy_blocks as cb`) — runnable standalone
with just `pip install classy_blocks`, indistinguishable from a hand-written
script, savable/editable/version-controllable.

**Avoiding duplicated/intermediate data models** — "recording subclasses":

For each supported classy_blocks construct (starting with `Box`), define a thin
subclass in classy_foundry, e.g. `classy_foundry.elements.Box(cb.Box)`, that:

- Has the *same* `__init__` signature as `cb.Box`, but stashes the raw
  constructor args (cb's `__init__` does math and discards the originals — we
  need them back for codegen/property display).
- Wraps `.chop()`, `.set_patch()`, etc. to record each call's args in an ordered
  log, while still calling `super()` so the object remains a fully functional
  `cb.Box`.
- Has a `to_lines(varname)` method emitting this object's Python source: the
  constructor call + one line per recorded config call.

One class definition then serves **three roles**:

1. **Live preview** — it *is* a real `cb.Box`/`cb.Operation`, so it can go
   straight into a `cb.Mesh`, get `.assemble()`'d, etc.
2. **FreeCAD property schema** — the Document Object's Proxy holds this instance;
   Properties are generated by introspecting the `__init__` signature + recorded
   chop/patch calls (small per-class metadata dict supplies labels/enum choices
   for the property editor).
3. **Script codegen** — `to_lines()` is the source text.

**What "recording" means**: not an imperative macro (a trace of actions to
replay onto existing state), but a declarative recipe — the recorded
constructor args plus the ordered chop/patch/etc. log fully describe the
object from scratch, so replaying them is idempotent and order-independent.
This is what makes `execute()`-based rebuild (below) safe on every recompute,
and what makes the recorded log directly printable as valid classy_blocks
source — the call-based syntax is just classy_blocks' own API for expressing
recipe fields (`chop()`/`set_patch()` are "named fields" expressed as method
calls rather than constructor kwargs).

**Document Object lifecycle — Properties as source of truth**: FreeCAD
Properties are what's persisted/restored, not the recording-subclass instance
itself. `execute()` (recompute) rebuilds a fresh instance from current
Property values every time: constructor-arg properties feed `__init__`, then
the recorded chop/patch/etc. log (stored as an ordered list in an opaque
`PropertyPythonObject`, edited only via the dedicated chop/patch panel —
Layer 3) is replayed. The resulting live `cb.*` instance feeds Tier A/B
preview and `to_lines()`. Constructor-arg properties are individual typed
FreeCAD Properties (auto-generated from `__init__` signature + per-class
metadata) and get the normal property-editor UI.

Where a construct references another (e.g. `Loft(bottom_face, top_face)`), the
reference is an `App::PropertyLink`; `execute()` pulls the referenced object's
freshly-rebuilt instance. Script generation topologically orders statements by
these references — FreeCAD's own dependency graph (`InList`/`OutList`, used
for recompute ordering) provides this for free.

**Loading a script (round-trip)**: exec the script's source with
`classy_blocks`'s names substituted for the recording subclasses (module/
namespace substitution — script text is unchanged, still says
`import classy_blocks as cb`). As long as the script follows the natural
"create → configure → `mesh.add()`" idiom already used in classy_blocks' own
README examples, the execution trace reconstructs the element list directly.
Generated scripts stay pure/portable; round-trip works for classy_foundry-style
(and most hand-written) scripts, with no guarantee for arbitrary/complex control
flow.

Optional secondary mechanism: trailing comments (e.g.
`# classy_foundry: label="Inlet duct"`) could carry FreeCAD-only presentation
metadata (display name, tree grouping/order) that classy_blocks has no concept
of — not the primary linking mechanism, just an escape hatch.

**Scope decision**: one-way (FreeCAD → script) is primary; round-trip load is a
planned capability via the exec-trace mechanism above, not full Python parsing.

**Starting construct**: `Box` (`cb.Box(point1, point2)`) — simplest Operation
subclass, minimal vertical slice covering `chop()` and `set_patch()`.

**Units**: plain unitless numbers throughout — dimensional properties (Tier 0
Point coordinates, lengths, etc.) are `App::PropertyFloat`, with no
FreeCAD-unit conversion at the classy_blocks boundary. Users needing a scale
factor use classy_blocks' own `mesh.settings.scale`, same as any hand-written
script. `PropertyFloat` still supports Spreadsheet expression-binding, so
parametrization (see Tier 0 below) is unaffected.

---

## Layer 3 — GUI (FreeCAD workbench)

### Display strategy — two-tier preview, no VTK file I/O

`write/vtk.py`'s `mesh_to_vtk` (debug output) needs nothing more than each
block's 8 corner vertices connected as straight edges — it deliberately ignores
curved edges (it's a topology-debug view). That same data can be built directly
as native `Part::Solid` shapes instead of writing-then-reading VTK:

- **Tier A — active element preview**: accurate geometry for the *single*
  element currently being edited, built via FreeCAD's `Part.makeLoft` /
  `Part.Extrude` / `Part.Revolve` etc. from the operation's actual Face/Edge data
  — classy_blocks edge types (Line/Arc/Spline/Project/...) map almost 1:1 onto
  `Part.Edge` types. Only one block, so this is cheap and gives a true "what will
  this actually look like" view.
- **Tier B — overall blocking overview**: cheap straight-edge hexahedra, one per
  block, from `mesh.assemble()`'s vertices/blocks (same data `mesh_to_vtk`
  consumes) — built as native `Part::Solid`/compound shapes for FreeCAD's normal
  3D view (selection, hide/show, standard navigation "for free"). Optionally
  colored per-face by patch via `DiffuseColor`.

True curved-edge geometry for the *whole* mesh is not pursued — Tier A covers the
"does this operation look right" need; Tier B covers the "does the overall
blocking/connectivity look right" need, matching how classy_blocks users already
use `debug.vtk` in ParaView today, just rendered natively.

### Interaction model

- **Tree view + property editor as the primary surface** (the FreeCAD paradigm
  users already know from Part/PartDesign): each classy_blocks element is one
  Document Object; its Properties come directly from Layer 2's recording-subclass
  reflection (constructor args, chops, patches).
- **Task-panel dialogs for creation**, with sensible live-previewed defaults,
  rather than "Add Box" buttons that drop a blank default object.
- **Dedicated chop/patch editor**: the genuinely novel part with no FreeCAD
  precedent and the actual source of today's crypticness — a panel showing a
  block's edges/faces by name (not raw integer axis/orientation indices), with 3D
  highlighting on hover so users never need to memorize axis/orientation
  conventions.

### Object hierarchy ("tiers") in the GUI

Mirrors classy_blocks' actual structure (see also Layer 1 unification above,
which collapses these from 4 families to 2 over time):

- **Tier 0 — Points (deferred)**: a lightweight, shareable Document Object
  wrapping a single coordinate, giving classy_blocks' otherwise-anonymous
  coordinate args (Box corners, Face points, etc.) an identity that can be
  shared/referenced and expression-bound to a `Spreadsheet`. Tier 1/2
  point-valued constructor-arg properties would become `App::PropertyLink`/
  `PropertyLinkSub` to a Tier 0 Point, with a literal-value fallback for the
  common case. Out of scope for now — Tier 1/2 objects use plain
  `App::PropertyVector`s for coordinates; revisit once Tier 1/2 are more
  fleshed out and the connectivity/codegen motivations below become concrete
  pain points:
  - **Codegen for shared points**: a Point referenced by multiple constructs
    (or a coordinate expression-bound to a spreadsheet cell referenced from
    multiple Points) would emit as one shared Python variable, used in each
    construct's call — preserving the "shared point" relationship as ordinary
    Python variable reuse (classy_blocks has no native shared-point concept,
    but this produces idiomatic, DRY output). A parameters block at the top of
    the generated script would mirror the spreadsheet cells actually
    referenced.
  - **Connectivity motivation**: shared Tier 0 Points would ensure block
    corners that should coincide for `mesh.assemble()`'s vertex-merging
    actually do exactly — no floating-point near-misses from independently
    -typed literals.
- **Tier 1 — 2D reusable profiles**: `Face` / `Sketch`. No chop/patch/cell info,
  purely geometric. Modeled like a FreeCAD Sketch object: standalone, reusable,
  referenceable by multiple Tier 2 objects (classy_blocks explicitly supports
  reusing a Face/Sketch across operations — "use existing Operation's Face to
  generate a new Operation", Connector between two existing Operations, chaining
  a Shape's end sketch into a new Shape).
- **Tier 2 — 3D "addable" things**: `Operation` / `Shape` (and `Stack`/
  `Assembly` as collections-of-shapes with their own chop/patch delegation
  rules). Modeled like PartDesign Pad/Pocket/Revolution: holds Link
  property/properties to one or two Tier 1 objects, plus sweep parameters
  (amount/angle/axis, or a second face for Loft). Carries chop, patch,
  projection, cell-zone configuration.
- **Root**: `Mesh` — top-level container (`mesh.add()`, `merge_patches`,
  `default_patch`, `geometry` dict).

### Optimization

Maps onto the same tiers as separate commands, not new object types:

- `SketchOptimizer` / `SketchSmoother` → command on a Tier 1 object (2D, before
  it's consumed by a Shape).
- `ShapeOptimizer` → command on a Tier 2 Shape's `.operations` (3D).
- `MeshOptimizer` / `MeshSmoother` → global command on the root `Mesh`.

---

## v1 scope for classy_foundry

One full vertical slice through **Tier 1 → Tier 2 → Root**: `Face` +
`Box`/`Loft`/`Extrude`/`Revolve`/`Wedge` + `Mesh` (Tier 0 Points deferred, see
above). This establishes the Document Object base patterns —
Properties-as-source-of-truth with `execute()`-rebuild, link properties,
chop/patch sub-editor, two-tier preview, script codegen with topological
ordering via FreeCAD's dependency graph — so that Sketch/Shape/Stack/Assembly/
Optimizer/Tier 0 Points slot into the *same* patterns later rather than
needing new ones.

---

## Reference: classy_blocks source map (as of this writing)

- `src/classy_blocks/__init__.py` — public API surface (`cb.*` exports).
- `src/classy_blocks/mesh.py` — `Mesh`: `add()`, `assemble()`, `grade()`,
  `write()`, `merge_patches()`, `set_default_patch()`, `add_geometry()`.
- `src/classy_blocks/construct/operations/operation.py` — `Operation` base:
  `chop()`, `chop_edge()`, `set_patch()`, `project_*()`, `set_cell_zone()`,
  `edges`, `patch_names`.
- `src/classy_blocks/construct/operations/{box,extrude,revolve,wedge,loft}.py`
- `src/classy_blocks/construct/flat/face.py` — `Face`: 4 points + 4 edges.
- `src/classy_blocks/construct/flat/sketch.py` — `Sketch` ABC: `faces`, `grid`,
  `chops: ClassVar`.
- `src/classy_blocks/construct/shape.py` — `Shape` ABC, `LoftedShape`,
  `ExtrudedShape`, `RevolvedShape`.
- `src/classy_blocks/construct/stack.py` — `Stack`, `TransformedStack`,
  `ExtrudedStack`, `RevolvedStack`.
- `src/classy_blocks/optimize/optimizer.py` — `MeshOptimizer`, `ShapeOptimizer`,
  `SketchOptimizer`.
- `src/classy_blocks/write/vtk.py` — `mesh_to_vtk` (debug output).
- `src/classy_blocks/base/element.py` — `ElementBase`: shared
  translate/rotate/scale/mirror/transform/`parts`/`center`.

---

## Next steps

1. **Now**: pursue the Layer 1 unification (Face/Sketch, Operation/Shape) as its
   own effort in the `classy_blocks` repo — separate planning session.
2. **Then**: return to classy_foundry and begin v1 (Face → Operation → Mesh),
   informed by whatever the unification settles on.
3. **Pending cleanup**: rename `freecad/classy_mason/` →
   `freecad/classy_foundry/` and `pyproject.toml` `name = "classy_mason"` →
   `"classy_foundry"`.
