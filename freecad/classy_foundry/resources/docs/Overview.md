<!-- SPDX-License-Identifier: MIT -->

# classy_foundry

A FreeCAD workbench to interactively and visually build
[classy_blocks](https://github.com/damogranlabs/classy_blocks) meshes for OpenFOAM's `blockMesh`.

classy_blocks is a powerful Python library for generating block-structured hexahedral meshes,
but its scripting-only interface can be cryptic for newcomers. classy_foundry wraps it in a
guided, visual FreeCAD workbench: build up a mesh from points, profiles and operations in the
3D view, preview the result, and export an idiomatic classy_blocks script.
