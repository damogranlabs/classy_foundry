"""App-level entry point (FreeCAD's Init.py equivalent).

Runs in both GUI and console mode. Document Object Proxies backed by
classy_blocks live under `objects/`, kept importable from here so documents
containing them can be opened headlessly (e.g. via `FreeCADCmd`) without the
GUI-only `init_gui` module.
"""
