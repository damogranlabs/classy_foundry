"""Tier 1 'MappedSketch' Document Object: a cb.MappedSketch defined by a point/quad sketcher."""

import numpy as np
import classy_blocks as cb
import FreeCAD
import Part

from .recording import ProxyBase, ViewProviderBase


def _apply_relational(points_data):
    """Compute positions, applying midpoint/average relational rules in-order."""
    positions = [list(p["pos"]) for p in points_data]
    for i, pt in enumerate(points_data):
        rel = pt.get("relational")
        if rel and rel.get("indices"):
            refs = [positions[j] for j in rel["indices"]]
            positions[i] = list(np.mean(refs, axis=0))
    return positions


def sketch_preview_shape(sketch):
    faces = []
    for face in sketch.faces:
        corners = [FreeCAD.Vector(*p.position) for p in face.points]
        wire = Part.makePolygon([*corners, corners[0]])
        try:
            faces.append(Part.Face(wire))
        except Exception:
            faces.append(wire)
    if not faces:
        return Part.Shape()
    return Part.makeCompound(faces)


class MappedSketchProxy(ProxyBase):
    def __init__(self, obj):
        obj.Proxy = self

        obj.addProperty(
            "App::PropertyPythonObject", "SketchPoints", "ClassyFoundry",
            "List of point dicts: pos, clamp, curve_idx, relational",
        )
        obj.SketchPoints = []

        obj.addProperty(
            "App::PropertyPythonObject", "SketchQuads", "ClassyFoundry",
            "List of [p0, p1, p2, p3] index lists",
        )
        obj.SketchQuads = []

        obj.addProperty(
            "App::PropertyLinkList", "Curves", "ClassyFoundry",
            "Curve objects referenced by OnCurve/OnSurface points",
        )

        obj.addProperty(
            "App::PropertyVector", "WorkOrigin", "Sketch",
            "Origin of the sketch work plane",
        )
        obj.addProperty(
            "App::PropertyVector", "WorkNormal", "Sketch",
            "Normal of the sketch work plane (default: Z-up = XY plane)",
        )
        obj.WorkNormal = FreeCAD.Vector(0, 0, 1)

    def execute(self, obj):
        points_data = obj.SketchPoints
        quads_data = obj.SketchQuads
        if not points_data or not quads_data:
            return

        positions = _apply_relational(points_data)
        self.sketch = cb.MappedSketch(positions, [list(q) for q in quads_data])
        obj.Shape = sketch_preview_shape(self.sketch)

    def to_lines(self, obj, varname):
        points_data = obj.SketchPoints
        quads_data = obj.SketchQuads
        if not points_data or not quads_data:
            return []

        positions = _apply_relational(points_data)
        pos_repr = [[round(c, 6) for c in p] for p in positions]
        return [
            f"positions_{varname} = {pos_repr}",
            f"{varname} = cb.MappedSketch(positions_{varname}, {[list(q) for q in quads_data]})",
        ]


class MappedSketchViewProvider(ViewProviderBase):
    def doubleClicked(self, vobj):
        import FreeCADGui
        from ..taskpanels.sketch_panel import SketchTaskPanel
        FreeCADGui.Control.showDialog(SketchTaskPanel(vobj.Object))
        return True


def make_mapped_sketch(doc, name="MappedSketch"):
    """Create a new MappedSketch Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    MappedSketchProxy(obj)
    if FreeCAD.GuiUp:
        MappedSketchViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
