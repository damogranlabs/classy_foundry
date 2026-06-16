"""Shared helpers for 'recording' classy_blocks Operation subclasses and their proxies.

cb.Box, cb.Loft, cb.Extrude, cb.Revolve (and later cb.Wedge, ...) are all
cb.Operation subclasses and share the same chop()/set_patch() surface, as well
as the same FreeCAD ChopCount*/Patch* properties. This module factors that
shared surface out so each RecordingX/XProxy pair only has to deal with its
own constructor arguments.
"""

import FreeCAD
import Part

CHOP_PATCH_SIDES = ("Bottom", "Top", "Left", "Right", "Front", "Back")


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

    def getIcon(self):
        return ""

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


def _resolve(obj, attr):
    """Return getattr(obj.Proxy, attr), recomputing obj if needed; None if unavailable."""
    if obj is None:
        return None
    if not hasattr(obj.Proxy, attr):
        obj.recompute(True)
    return getattr(obj.Proxy, attr, None)


def resolve_face(face_obj):
    """Return face_obj's recording Face instance, recomputing if needed; None if unavailable."""
    return _resolve(face_obj, "face")


def resolve_operation(op_obj):
    """Return op_obj's recording Operation instance, recomputing if needed; None if unavailable."""
    return _resolve(op_obj, "operation")


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
        apply_chop_patch(obj, operation)
        self.operation = operation
        obj.Shape = loft_preview_shape(operation)

        for name in self.FACE_LINKS:
            hide(getattr(obj, name))


class OperationViewProviderBase(ViewProviderBase):
    """Shared claimChildren() for Tier 2 Operation view providers: nests linked Face(s)."""

    def claimChildren(self):
        obj = self.Object
        children = []
        for name in obj.Proxy.FACE_LINKS:
            face_obj = getattr(obj, name)
            if face_obj is not None and face_obj not in children:
                children.append(face_obj)
        return children


class RecordingOperationMixin:
    """Records chop()/set_patch() calls (and referenced Faces) for later codegen."""

    def __init__(self, *args, **kwargs):
        self.recorded_chops: list[tuple[int, dict]] = []
        self.recorded_patches: list[tuple[str, str]] = []
        self.referenced_faces: dict = {}
        super().__init__(*args, **kwargs)

    def chop(self, axis, **kwargs):
        super().chop(axis, **kwargs)
        self.recorded_chops.append((axis, kwargs))

    def set_patch(self, sides, name):
        super().set_patch(sides, name)
        self.recorded_patches.append((sides, name))

    def chop_patch_lines(self, varname: str) -> list[str]:
        """Codegen lines for recorded chop()/set_patch() calls, in recording order."""
        lines = []
        for axis, kwargs in self.recorded_chops:
            args = ", ".join(f"{key}={value!r}" for key, value in kwargs.items())
            lines.append(f"{varname}.chop({axis}, {args})")
        for sides, name in self.recorded_patches:
            lines.append(f"{varname}.set_patch({sides!r}, {name!r})")
        return lines


def add_chop_patch_properties(obj):
    """Add the standard ChopCountX/Y/Z and Patch* properties to a Tier 2 object."""
    for axis_name in ("X", "Y", "Z"):
        obj.addProperty(
            "App::PropertyInteger",
            f"ChopCount{axis_name}",
            "Chop",
            f"Number of cells along the {axis_name} axis (0 = not chopped)",
        )
    for side in CHOP_PATCH_SIDES:
        obj.addProperty(
            "App::PropertyString",
            f"Patch{side}",
            "Patches",
            f"Patch name for the '{side.lower()}' side (empty = not set)",
        )


def apply_chop_patch(obj, operation):
    """Replay an object's ChopCount*/Patch* properties onto a recording operation."""
    for axis, axis_name in enumerate(("X", "Y", "Z")):
        count = getattr(obj, f"ChopCount{axis_name}")
        if count > 0:
            operation.chop(axis, count=count)
    for side in CHOP_PATCH_SIDES:
        name = getattr(obj, f"Patch{side}")
        if name:
            operation.set_patch(side.lower(), name)


def loft_preview_shape(operation) -> Part.Shape:
    """Straight-edge preview (Tier B) lofted between an operation's bottom and top faces."""
    bottom = [FreeCAD.Vector(*p.position) for p in operation.bottom_face.points]
    top = [FreeCAD.Vector(*p.position) for p in operation.top_face.points]
    bottom_wire = Part.makePolygon([*bottom, bottom[0]])
    top_wire = Part.makePolygon([*top, top[0]])
    return Part.makeLoft([bottom_wire, top_wire], True)


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
