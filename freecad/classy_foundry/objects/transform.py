"""Transform Document Object: applies translate/rotate/scale to a source cb entity."""

import math

import FreeCAD

from .recording import (
    ENTITY_ATTRS, ProxyBase, ViewProviderBase, _ENTITY_PREVIEW, modifier_root_from, resolve_entity,
)

TRANSFORM_TYPES = ["Translate", "Rotate", "Scale"]


class TransformProxy(ProxyBase):
    IS_MODIFIER = True

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLink", "Source", "ClassyFoundry",
            "Object to transform",
        )
        obj.addProperty(
            "App::PropertyEnumeration", "TransformType", "Transform",
            "Type of transformation",
        )
        obj.TransformType = list(TRANSFORM_TYPES)

        obj.addProperty(
            "App::PropertyVector", "Displacement", "Translate",
            "Translation vector",
        )

        obj.addProperty(
            "App::PropertyFloat", "Angle", "Rotate",
            "Rotation angle (degrees)",
        )
        obj.addProperty(
            "App::PropertyVector", "Axis", "Rotate",
            "Rotation axis",
        ).Axis = FreeCAD.Vector(0, 0, 1)
        obj.addProperty(
            "App::PropertyVector", "RotateOrigin", "Rotate",
            "Center of rotation",
        )

        obj.addProperty(
            "App::PropertyFloat", "Ratio", "Scale",
            "Scale factor",
        ).Ratio = 1.0
        obj.addProperty(
            "App::PropertyVector", "ScaleOrigin", "Scale",
            "Center of scaling",
        )

    def execute(self, obj):
        source = obj.Source
        if source is None:
            return

        attr, original = resolve_entity(source)
        if original is None:
            return

        transformed = original.copy()
        _apply(obj, transformed)

        for a in ENTITY_ATTRS:
            if a != attr and hasattr(self, a):
                delattr(self, a)
        setattr(self, attr, transformed)

        obj.Shape = _ENTITY_PREVIEW[attr](transformed)

    def to_lines(self, obj):
        root = modifier_root_from(obj.Source)
        if root is None:
            return []
        call = _transform_call(obj)
        return [f"{root.Name.lower()}.{call}"]


class TransformViewProvider(ViewProviderBase):
    pass


def _apply(obj, target):
    """Apply the transform described by obj's properties to a cb target."""
    t = obj.TransformType
    if t == "Translate":
        d = obj.Displacement
        target.translate([d.x, d.y, d.z])
    elif t == "Rotate":
        a = obj.Axis
        o = obj.RotateOrigin
        target.rotate(math.radians(float(obj.Angle)), [a.x, a.y, a.z], [o.x, o.y, o.z])
    elif t == "Scale":
        o = obj.ScaleOrigin
        target.scale(obj.Ratio, [o.x, o.y, o.z])


def _transform_call(obj):
    """Return the codegen method call string for obj's transform."""
    t = obj.TransformType
    if t == "Translate":
        d = obj.Displacement
        return f"translate([{d.x}, {d.y}, {d.z}])"
    if t == "Rotate":
        a = obj.Axis
        o = obj.RotateOrigin
        angle = round(math.radians(float(obj.Angle)), 6)
        return f"rotate({angle}, [{a.x}, {a.y}, {a.z}], [{o.x}, {o.y}, {o.z}])"
    if t == "Scale":
        o = obj.ScaleOrigin
        return f"scale({obj.Ratio}, [{o.x}, {o.y}, {o.z}])"
    return ""


def make_transform(doc, name="Transform"):
    """Create a new Transform Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    TransformProxy(obj)
    if FreeCAD.GuiUp:
        TransformViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
