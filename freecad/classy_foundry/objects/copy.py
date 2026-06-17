"""Copy Document Object: a linked copy of another cb entity."""

import FreeCAD

from .recording import ProxyBase, ViewProviderBase, solid_preview_shape

SOLID_ATTRS = ("operation", "shape")


class CopyProxy(ProxyBase):
    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLink", "CopyOf", "ClassyFoundry",
            "Source object to copy (stays linked)",
        )

    def execute(self, obj):
        source = obj.CopyOf
        if source is None:
            return

        attr, original = _resolve_source(source)
        if original is None:
            return

        copied = original.copy()

        for a in SOLID_ATTRS:
            if a != attr and hasattr(self, a):
                delattr(self, a)
        setattr(self, attr, copied)

        obj.Shape = solid_preview_shape(copied)

    def to_lines(self, obj, varname):
        source = obj.CopyOf
        if source is None:
            return []
        target = source
        while hasattr(target, "TransformType") and target.Source is not None:
            target = target.Source
        return [f"{varname} = {target.Name.lower()}.copy()"]


class CopyViewProvider(ViewProviderBase):
    pass


def _resolve_source(source):
    """Return (attr_name, cb_solid) from a source object, recomputing if needed."""
    for attr in SOLID_ATTRS:
        val = getattr(source.Proxy, attr, None)
        if val is not None:
            return attr, val
    source.recompute(True)
    for attr in SOLID_ATTRS:
        val = getattr(source.Proxy, attr, None)
        if val is not None:
            return attr, val
    return None, None


def make_copy(doc, name="Copy"):
    """Create a new Copy Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    CopyProxy(obj)
    if FreeCAD.GuiUp:
        CopyViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
