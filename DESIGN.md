# classy_foundry — Design

A topology editor for [`classy_blocks`](https://github.com/damogranlabs/classy_blocks),
built on [Polyscope](https://polyscope.run/py/).

Building *everything* with the mouse takes more steps and more time than scripting it.
What scripting can't do well is 3D block **topology**: a point/quad net is fine with pen
and paper in 2D, but laying out points and their connectivity in 3D is painful, and
maintaining indices by hand as points come and go is worse. So this tool authors nothing
but topology — points, blocks, patches — and everything else (chops, grading, assembly,
writing `blockMeshDict`) stays in the user's script, where it is fast.

**Foundry never writes a `blockMeshDict`.** Coordinates it produces are *hints*, not
truth: `MappedShape` maps patch faces onto real surfaces and optimises afterwards. There
is no CAD kernel, no work planes, no precision snapping.

The design decisions and the reasoning behind them live in
`docs/superpowers/specs/2026-09-19-topology-editor-design.md`.

---

## Running

- **Edit** (a terminal program, from `src/`):
  `python -m classy_foundry impeller.shape [blade.stl hub.stl ...]` — opens the file, or
  starts a new one if it doesn't exist yet. Any further arguments are reference surfaces.
- **Use** (from any script; note it does *not* import foundry):
  ```python
  import classy_blocks as cb
  from classy_foundry.description import MappedShapeDescription   # → classy_blocks, later

  description = MappedShapeDescription.load("impeller.shape")
  shape = cb.MappedShape(description.points, description.hexas)
  ```
- **Environment**: venv at `/home/nejc/venv/classy_foundry/bin/python` (**not** in-repo).
  Verified against polyscope 2.6.1 (with full `polyscope.imgui` bindings), classy_blocks
  1.11.2, trimesh, numpy, Python 3.10. The package floor is 3.9, so annotations use
  `Optional[X]`, never `X | Y`.

The editor is reachable **only** from the command line. It is not called from a meshing
script: that script runs dozens of times and the editor would block every run, and it
would force the script to be re-edited to change anything about the topology. Nothing
imports `classy_foundry` as a library — `__init__.py` is empty on purpose.

## Reference surfaces

An STL is loaded by **dragging it onto the window** (Polyscope's `set_files_dropped_callback`
— there is no file dialog in Polyscope or its imgui, and this is better than one), or by
naming it on the command line. Either way it becomes a patch named after the file
(`blade.stl` → `blade`) carrying it as its surface, so it is saved with the document and
comes back next session without the argument. Dropping the same name again re-points that
one patch rather than adding another, and a patch that already has faces simply gains the
surface.

The mesh is what points snap to (`Ctrl` during a move) and what the topology is built
against. A path whose file has moved is skipped rather than raising — paths arrive from
drops, the command line and a text field, so a bad one must not kill the frame callback —
and the patch panel says so in red.

## SpaceMouse

A 3Dconnexion puck drives **the camera only** — points and blocks stay the mouse's job —
and it is optional: if `spacenavd` isn't running, `Navigator.attach()` returns `None` and
nothing else changes.

It talks to spacenavd's UNIX socket directly, with no `libspnav`, no ctypes and no new
dependency: a packet is eight little-endian `int32`s, `[type, x, y, z, rx, ry, rz, period]`,
type 0 for motion, and a proto-v0 client receives motion events with no handshake
(spacenavd `src/proto_unix.c`, `src/client.c`). Axis values are the puck's *absolute*
deflection, so a poll keeps the newest packet and drops the backlog — accumulating would
build a lag the hand can feel.

**Two modes**, the classic 3Dconnexion split, chosen in the Navigation panel. They differ
in what the rotation pivots about, what a dolly does, and the sign of every axis:

- **Object** (the default): the puck moves *the model*. Push right and the model goes
  right, so the camera goes left; rotation orbits the model, which stays in the middle of
  the view; a dolly changes the distance and is clamped, so you can never zoom through the
  thing you are building.
- **Camera**: the puck moves *the eye*. Push right and the camera goes right; rotation
  turns the gaze from where it stands; a dolly flies, target and all, through the scene.

They are two small strategy classes, so `navigate` asks the mode rather than branching on
it. Both preserve `up`, so the horizon never rolls and the model never ends up upside
down — which is why puck roll (rz) is unmapped.

| deflection | object mode | camera mode |
|---|---|---|
| x / y | slide the model sideways / vertically | pan the eye |
| z | pull the cap back to push the model away | fly backwards |
| rx | tilt the model (clipped short of the pole) | look up/down |
| ry | spin the model about `up` | look left/right |
| rz | unused | unused |

Speeds are in **scene extents per second** (`Document.extent`), so a blade and a bridge
handle the same. Every sensitivity is signed, and the panel's sliders run through
zero: **a negative value inverts that axis**, which is the fix when one control feels
backwards in an otherwise correct mode. Tuning is live, because the feel of this cannot be
read off a number.

The only state is how far ahead the pivot sits; position and direction are read from
polyscope every frame, and the camera is written back only while the puck is deflected. So
ordinary mouse navigation and the puck cooperate — a mouse orbit simply carries the pivot
along in front of the camera — and a still device never overrides the mouse.

## The work plane

Where a click lands, and what the scene is cut against. It is **polyscope's own slice
plane**, not state of ours: polyscope already gives it a pose, a drawn grid, transparency,
colour, a draggable widget and per-structure exemptions, so its pose is the single source
of truth — dragging the widget, typing numbers and following the camera all write to the
same place, and `WorkPlane.plane` hands it back as an ordinary `geom.Plane`.

Three things are ours, because polyscope cannot know them:

- **Follow or stay** (`W` when idle). Following lays it across the view at the pivot, which
  is good for aiming; locked is what lets several points be placed *on one plane* — if it
  rotated with the camera, coplanar points would be impossible.
- **Numbers.** Origin and normal in the panel, live only while locked; typing into them
  while following would be overwritten the next frame. Three buttons give XY/XZ/YZ.
- **What may be cut.** Points and the move gizmo never are, or the plane would eat the very
  things being placed.

An **inactive slice plane cannot hold a pose** — polyscope parks it at infinity — so the
plane is always active and "does it cut?" is expressed by exempting structures. That is why
`scene.sync` returns its structures by name: the work plane needs them after every rebuild.

During a move, `W` constrains onto the work plane *itself* (not a plane through the
selection, as `X`/`Y`/`Z` do), so the points land on it. Snapping then traces where that
plane cuts the reference surface — set the plane, constrain, hold Ctrl, and you are drawing
along a section of the STL.

## The document

The topology is an object graph in which **nothing above `storage.py` holds an index**.
Adding or deleting a point renumbers nothing, because there are no numbers.

```python
Point(position)                       # a vertex; a hint, not precision geometry
Cell(points)                          # 8 points (hex) or 4 (quad — the MappedSketch case)
Patch(name, faces, surface)           # faces are 4-point tuples; surface is a file path
```

`Point`, `Cell` and `Patch` are `@dataclass(eq=False)`, so `==` is identity and they stay
hashable. Identity *is* the data model. Deleting a point cascades to the cells and patch
faces that reference it, the way deleting a vertex takes its faces with it in Blender.

Two consequences worth knowing:

- **A face is never a construction entity** — only a 4-point tuple identifying a patch
  face. Blocks are built from points directly, in the order they were clicked, which is
  blockMesh vertex ordering and therefore the contract with `MappedShape`.
- **A patch with a surface and no faces is a backdrop** — that is how an STL loaded to
  build against is represented, so no separate surfaces collection exists anywhere.
  Conversely, a patch with faces and no surface is a plain boundary (an inlet).

## The file

JSON, `.shape` extension, written and read by `MappedShapeDescription.save`/`.load`:

```json
{
 "points":   [[0.0, 0.0, 0.0], ...],
 "hexas":    [[0, 1, 2, 3, 4, 5, 6, 7], ...],
 "patches":  {"top": [[8, 9, 10, 11]]},
 "surfaces": {"top": "blade.stl"}
}
```

One point, block and face per line, so a diff shows a moved point or a new block as a
single changed row (`_one_per_line` collapses `json.dumps`' exploded numeric arrays; the
result is still ordinary JSON). Surface paths are stored **relative to the `.shape` file**,
so a project directory stays movable. `patches` and `surfaces` share their keys.

`description.py` is **destined for classy_blocks** — a `.shape` file is a classy_blocks
document and nobody should have to install foundry (and a GPU stack) to read one. It
therefore imports nothing from foundry, and moving it is a file move. `MappedShape` taking
a description rather than `(points, hexas)` is the matching change on that side.

## The editor

Blender's modal grammar, because it is the muscle memory of the people who would use this.
One departure: **delete is `Delete`, not `X`**, since `X` already constrains a move to the
X axis.

| Key | Operation |
|-----|-----------|
| `P` | place a point — on the surface under the cursor, else on the work plane |
| `W` | work plane: follow the camera or stay put (during a move: constrain onto it) |
| click / Shift+click | select a point **or a block** / add to the selection, or toggle it out |
| click empty space | deselect everything (Shift+click on nothing keeps the selection) |
| `Escape` | deselect everything (during a move it cancels the move instead) |
| `C` | duplicate the selection and move the copies (Esc discards them) |
| `G` | move the selection |
| `X`/`Y`/`Z` | during a move: constrain to that axis |
| `Shift+X/Y/Z` | during a move: constrain to the plane *excluding* that axis (`Shift+Z` = XY) |
| Ctrl (held) | during a move: snap to the surface under the cursor |
| `Esc` / click | during a move: cancel / confirm |
| `B` | make a block from 8 selected points (or 4, for a sketch quad) |
| `Delete` | delete selected blocks (their points stay), and selected points with the blocks and patch faces using them |
| `Ctrl+S` | save |

`C` exists because placing every point from scratch starts it wherever the ground plane
is, which is never where it belongs; copying a point that is already right and nudging it
is far less work. The copies go straight into the move modal, so they are never left
stacked on their originals — confirming has moved them, and cancelling deletes them. The
points a move *created* are tracked in `Editor.born`, which is empty for an ordinary move,
so cancelling one discards nothing without needing to ask which kind it was.

**Selection is an ordered list, not a set.** Click order is preserved and operations
consume it in that order — that is what gives the user control over vertex ordering
without the editor guessing at windings. Inverted or twisted blocks are the user's to see
and fix; a signed-volume check is a later addition.

**`keymap.py` is the single source for dispatch *and* the help window**, so the Tools
window cannot drift from what the keys actually do. Adding an operation is one row.

**Constraints are one protocol, two classes** (`geom.py`):

| | `from_ray(origin, direction)` | `project(point)` | `offset(distance)` | `allows(direction)` |
|---|---|---|---|---|
| `Plane` | ray ∩ plane | drop the off-plane component | zero — a number means nothing in a plane | the axes lying in the plane |
| `Axis` | closest point on the axis to the ray | foot of the perpendicular | along the direction | its own axis, either way |

Free move is not a special case: it is a `Plane` whose normal is the camera direction.
**Snapping intersects the geometry itself**, in `geom.py`, rather than asking polyscope
what is under the cursor: the point being dragged sits under the cursor, so a pick keeps
returning *it* (or a block) instead of the reference surface, and the point jumps between
the surface and the free solution. A trimesh ray cast costs about a millisecond and cannot
be occluded by our own structures.

Each constraint decides what snapping *means*, so `solve` asks rather than branches:

| constraint | snap target |
|---|---|
| `FreePlane` (a free move) | the ray's hit on the surface — the point slides over it |
| `Plane` (`Shift+X/Y/Z`) | the **cross-section** that plane cuts, nearest point to the ray — so a drag traces it |
| `Axis` (`X/Y/Z`) | the ray's surface hit, pulled back onto the axis |

A plane snaps to segments of the section, not to its vertices: a coarse mesh has few, and
snapping to those alone makes the cursor jump from corner to corner. The section is cut
once and cached for the life of the constraint — a new constraint is built whenever the
plane changes, so the cache cannot go stale. A snap that finds nothing falls back to the
ordinary ray solution, so the point keeps following the mouse instead of freezing.

**Blocks are selected by clicking them.** A pick reports the index of the face that was
hit, and `cell_owners` -- the cell each rendered face belongs to, in the order `hex_faces`
emits them -- turns that into the block, with no extra bookkeeping. Points are drawn on
top, so a click near one takes the point and a click elsewhere on a block takes the block.
Points and blocks share one click: a plain click starts a fresh selection of either kind,
Shift adds to whatever is there — or toggles it back out. Clicking empty space deselects
everything, but a Shift-click that hits nothing leaves the selection alone, since that is a
slip of the hand rather than an instruction to start over. `Escape` deselects too, except
during a move, where it cancels the move. Deleting a block leaves its points, since they are
usually wanted for whatever replaces it; deleting a point still takes its blocks.

**Two visual cues, and no more.** Selected points and selected blocks take a highlight colour (a per-point
colour quantity on the cloud). While a move is live -- and only then -- an axis gizmo is
drawn through the move's centroid: three world axes, each bright when the constraint
*allows* travel along it and dim otherwise. That question is asked of the constraint
(`allows(direction)`), so a `Shift+Z` plane lights X and Y, an `X` constraint lights X
alone, and an obliquely-viewed free move lights none -- which is what "unconstrained by
any world axis" looks like.

**Appearance is Polyscope's own business.** Transparency, edges and colours are in its
structure controls already, so foundry writes none of it.

## Modules

| Module | Responsibility |
|---|---|
| `document.py` | `Point`, `Cell`, `Patch`, `Document`; the add/delete cascade. No polyscope, no classy_blocks. |
| `description.py` | `MappedShapeDescription` + `FileSurface`, `save`/`load`. Destined for classy_blocks; imports nothing from foundry. |
| `storage.py` | `Document` ↔ description. **The only place indices exist.** |
| `transform.py` | `Move` — the modal move; knows nothing of mice, rays or polyscope. |
| `geom.py` | `ray_plane_hit`, `load_trimesh`, `Plane`, `Axis`. Pure. |
| `view/scene.py` | Renders a document: point cloud (selection coloured), one mesh of every cell's sides, a mesh per backdrop, and the move gizmo. |
| `view/keymap.py` | `Binding` + the table; dispatch and the help window. |
| `view/editor.py` | Ordered selection, operations, and `handle_frame` — the one place mouse/keyboard/camera enter. |
| `view/patches.py` | The patch panel: names, face counts, surface files. |
| `spacemouse.py` | spacenavd's socket protocol; `poll()` → the puck's current deflection. No polyscope. |
| `navigation.py` | Turntable camera math: a deflection applied to a `View`. Pure. |
| `view/navigator.py` | Wires the two to polyscope's camera. |
| `__main__.py` | The CLI. |

`view/` imports downward only; nothing outside `view/` imports polyscope.

## Testing

```bash
/home/nejc/venv/classy_foundry/bin/python -m pytest tests     # from the repo root
/home/nejc/venv/classy_foundry/bin/python -m ruff check .
```

`document`, `storage`, `description`, `geom` and `transform` are pure and tested directly.
The view layer is exercised headlessly with Polyscope's CPU mock:
`ps.set_allow_headless_backends(True)` + `ps.init('openGL_mock')` + `ps.frame_tick()`,
calling the inner draw functions directly (the user callback fires roughly once per process
in mock mode). Note `psim.GetIO()` segfaults outside an initialised imgui frame, so
anything touching it must run after a `frame_tick`.

## Not here (yet)

- **The extrude shortcut** — select four points, `E` duplicates them, appends
  `Cell(originals + copies)` and drops into the move modal on the copies. Three things
  already make it additive rather than a rewrite: selection is an *ordered list of points*,
  cell creation is a function of an ordered point list, and `begin_move` takes **any**
  point list plus a starting constraint rather than reading the selection itself.
- **Inverted-block detection** — a signed-volume check that flags, not repairs.
- **Morphing and optimisation data** — where per-point constraints would live, matching the
  `TODO` on the classy_blocks side. Surfaces currently bind per *patch*, not per point.
- **Rotate and scale** — deliberately absent: these are topology blueprints, not geometry.
