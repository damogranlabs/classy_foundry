"""Shared helpers for 'recording' classy_blocks Operation subclasses and their proxies."""

import FreeCAD
import Part

SOLID_ATTRS = ("operation", "shape")
ENTITY_ATTRS = (*SOLID_ATTRS, "sketch")


def resolve_solid(source):
    """Return (attr_name, cb_solid) from a source proxy (operations and shapes only)."""
    for attr in SOLID_ATTRS:
        val = getattr(source.Proxy, attr, None)
        if val is not None:
            return attr, val
    return None, None


def resolve_entity(source):
    """Return (attr_name, cb_entity) from any proxy type (operation, shape, or sketch)."""
    for attr in ENTITY_ATTRS:
        val = getattr(source.Proxy, attr, None)
        if val is not None:
            return attr, val
    return None, None


def modifier_root_from(source):
    """Walk source up through IS_MODIFIER proxies via Source links to the first non-modifier."""
    current = source
    while current is not None and getattr(current.Proxy, "IS_MODIFIER", False):
        current = getattr(current, "Source", None)
    return current


class ProxyBase:
    """Shared no-op persistence for Document Object proxies (state lives in Properties)."""

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class ViewProviderBase:
    """Shared minimal ViewProvider: just attaches and renders Shape with no custom icon."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def onDelete(self, vobj, subelements):
        return True

    def getIcon(self):
        return ""

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


def _resolve(obj, attr):
    """Return getattr(obj.Proxy, attr), or None if unavailable."""
    if obj is None:
        return None
    return getattr(obj.Proxy, attr, None)


def resolve_face(face_obj):
    """Return face_obj's recording Face instance, recomputing if needed; None if unavailable."""
    return _resolve(face_obj, "face")


def resolve_operation(op_obj):
    """Return op_obj's recording Operation instance, recomputing if needed; None if unavailable."""
    return _resolve(op_obj, "operation")


def resolve_sketch(sketch_obj):
    """Return sketch_obj's cb.MappedSketch instance, recomputing if needed; None if unavailable."""
    return _resolve(sketch_obj, "sketch")


def hide(obj):
    """Hide obj in the 3D view once it's been consumed by another object."""
    if FreeCAD.GuiUp:
        obj.ViewObject.Visibility = False


def flat_face_shape(face) -> Part.Shape:
    """Flat polygon preview (Tier B) for a cb.Face."""
    corners = [FreeCAD.Vector(*p.position) for p in face.points]
    wire = Part.makePolygon([*corners, corners[0]])
    return Part.Face(wire)


class FaceProxyBase(ProxyBase):
    """Shared execute() for Tier 1 Face proxies (Face, ExtractedFace, ...).

    Subclasses implement `build_face(obj)`, returning a cb.Face-like recording
    instance (with `.points` and `.to_lines()`), or None if not yet buildable.
    """

    def execute(self, obj):
        face = self.build_face(obj)
        if face is None:
            return

        self.face = face
        obj.Shape = flat_face_shape(face)


class OperationProxyBase(ProxyBase):
    """Shared execute() for Tier 2 Operation proxies (Box, Extrude, Loft, Revolve, ...).

    Every classy_blocks Operation is, in the end, a Loft between a bottom and a top
    Face - so resolving input Face(s), recording chop/patch, and building the Tier B
    preview is identical across operations. Subclasses just declare which of their
    properties are Face links via `FACE_LINKS` (in the order `build_operation` wants
    them) and implement `build_operation(obj, *faces)`.
    """

    FACE_LINKS: tuple[str, ...] = ()

    def execute(self, obj):
        faces = [resolve_face(getattr(obj, name)) for name in self.FACE_LINKS]
        if any(face is None for face in faces):
            return

        operation = self.build_operation(obj, *faces)
        self.operation = operation
        obj.Shape = self._preview_shape(obj, operation)

    def _preview_shape(self, obj, operation) -> Part.Shape:
        return loft_preview_shape(operation)


class OperationViewProviderBase(ViewProviderBase):
    pass


class AxisVisualizationMixin:
    """ViewProvider mixin that draws a revolve/sweep axis line during object editing.

    Subclasses declare which properties carry the origin point and axis direction
    via class attributes; both default to the names used by Revolve.
    """

    AXIS_ORIGIN_PROP = "Origin"
    AXIS_DIR_PROP = "Axis"
    _AXIS_DISPLAY_LENGTH = 5.0

    def setEdit(self, vobj, mode):
        from pivy import coin
        import FreeCADGui

        sep = coin.SoSeparator()
        col = coin.SoBaseColor()
        col.rgb = (1.0, 0.5, 0.0)
        style = coin.SoDrawStyle()
        style.lineWidth = 2.0
        self._axis_coords = coin.SoCoordinate3()
        sep.addChild(col)
        sep.addChild(style)
        sep.addChild(self._axis_coords)
        sep.addChild(coin.SoLineSet())
        self._axis_root = sep

        self._update_axis_line(vobj.Object)
        FreeCADGui.ActiveDocument.ActiveView.getSceneGraph().addChild(self._axis_root)
        return False

    def unsetEdit(self, vobj, mode):
        import FreeCADGui
        if hasattr(self, "_axis_root"):
            view = FreeCADGui.ActiveDocument.ActiveView
            if view is not None:
                view.getSceneGraph().removeChild(self._axis_root)
            del self._axis_root
            del self._axis_coords
        return False

    def updateData(self, obj, prop):
        if prop in (self.AXIS_ORIGIN_PROP, self.AXIS_DIR_PROP) and hasattr(self, "_axis_root"):
            self._update_axis_line(obj)

    def _update_axis_line(self, obj):
        a = getattr(obj, self.AXIS_DIR_PROP)
        length = (a.x ** 2 + a.y ** 2 + a.z ** 2) ** 0.5
        if length < 1e-10:
            return
        o = getattr(obj, self.AXIS_ORIGIN_PROP)
        half = self._AXIS_DISPLAY_LENGTH
        dx, dy, dz = a.x / length * half, a.y / length * half, a.z / length * half
        self._axis_coords.point.setValues(0, 2, [
            [o.x - dx, o.y - dy, o.z - dz],
            [o.x + dx, o.y + dy, o.z + dz],
        ])


class RecordingOperationMixin:
    """Records referenced Faces for later codegen."""

    def __init__(self, *args, **kwargs):
        self.referenced_faces: dict = {}
        super().__init__(*args, **kwargs)


def _cap_face_outward(pts, outward_hint):
    """Return a planar face from pts whose normal points in the outward_hint direction.

    makeLoft(..., solid=True) derives cap orientation from the wire winding, which
    flips sign when the top face has been rotated ≥90°.  Building caps explicitly
    and orienting them with this helper avoids that artefact entirely.
    """
    wire = Part.makePolygon([*pts, pts[0]])
    face = Part.Face(wire)
    if face.normalAt(0, 0).dot(outward_hint) < 0:
        wire = Part.makePolygon([*pts[::-1], pts[-1]])
        face = Part.Face(wire)
    return face


def loft_preview_shape(operation) -> Part.Shape:
    """Straight-edge preview (Tier B) lofted between an operation's bottom and top faces."""
    bottom = [FreeCAD.Vector(*p.position) for p in operation.bottom_face.points]
    top = [FreeCAD.Vector(*p.position) for p in operation.top_face.points]
    bottom_wire = Part.makePolygon([*bottom, bottom[0]])
    top_wire = Part.makePolygon([*top, top[0]])
    side_faces = list(Part.makeLoft([bottom_wire, top_wire], False).Faces)
    n = len(bottom)
    bc = FreeCAD.Vector(sum(p.x for p in bottom) / n, sum(p.y for p in bottom) / n, sum(p.z for p in bottom) / n)
    tc = FreeCAD.Vector(sum(p.x for p in top) / n, sum(p.y for p in top) / n, sum(p.z for p in top) / n)
    return Part.makeCompound(side_faces + [_cap_face_outward(bottom, bc - tc), _cap_face_outward(top, tc - bc)])


def revolve_preview_shape(operations, origin, axis, angle_deg) -> Part.Shape:
    """Preview for any revolved solid: sweeps each operation's bottom face with FreeCAD's native revolve."""
    solids = []
    for operation in operations:
        pts = [FreeCAD.Vector(*p.position) for p in operation.bottom_face.points]
        try:
            face = Part.Face(Part.makePolygon([*pts, pts[0]]))
            solids.append(face.revolve(origin, axis, angle_deg))
        except Exception:
            pass
    return Part.makeCompound(solids) if solids else Part.Shape()


def solid_preview_shape(solid) -> Part.Shape:
    """Preview shape for any cb solid (single Operation or multi-operation Shape)."""
    if hasattr(solid, "operations"):
        previews = []
        for op in solid.operations:
            try:
                previews.append(loft_preview_shape(op))
            except Exception:
                pass
        return Part.makeCompound(previews) if previews else Part.Shape()
    return loft_preview_shape(solid)


def sketch_preview_shape(sketch) -> Part.Shape:
    """Flat quad preview for a cb.MappedSketch (shown for Copy/Transform of a sketch)."""
    faces = []
    for face in sketch.faces:
        pts = [FreeCAD.Vector(*p.position) for p in face.points]
        try:
            faces.append(Part.Face(Part.makePolygon([*pts, pts[0]])))
        except Exception:
            pass
    return Part.makeCompound(faces) if faces else Part.Shape()


_ENTITY_PREVIEW = {
    "operation": solid_preview_shape,
    "shape": solid_preview_shape,
    "sketch": sketch_preview_shape,
}


def curve_preview_shape(curve) -> Part.Shape:
    """Wire preview for a curve, discretized into segments."""
    vectors = [FreeCAD.Vector(*p) for p in curve.discretize()]
    return Part.makePolygon(vectors)


def resolve_curve(curve_obj):
    """Return curve_obj's recording curve instance, recomputing if needed; None if unavailable."""
    return _resolve(curve_obj, "curve")


class CurveProxyBase(ProxyBase):
    """Shared execute() for Tier 0 Curve proxies.

    Subclasses implement build_curve(obj), returning an object with discretize()
    and to_lines(), or None if not yet buildable.
    """

    def execute(self, obj):
        curve = self.build_curve(obj)
        if curve is None:
            return
        self.curve = curve
        obj.Shape = curve_preview_shape(curve)
