"""Copy Document Object: a linked copy of another cb entity."""

import FreeCAD

from .recording import ENTITY_ATTRS, ProxyBase, ViewProviderBase, _ENTITY_PREVIEW, modifier_root_from, resolve_entity


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

        attr, original = resolve_entity(source)
        if original is None:
            return

        copied = original.copy()

        for a in ENTITY_ATTRS:
            if a != attr and hasattr(self, a):
                delattr(self, a)
        setattr(self, attr, copied)

        obj.Shape = _ENTITY_PREVIEW[attr](copied)

    def to_lines(self, obj, varname):
        source = obj.CopyOf
        if source is None:
            return []
        root = modifier_root_from(source)
        return [f"{varname} = {root.Name.lower()}.copy()"]


class CopyViewProvider(ViewProviderBase):
    pass


def make_copy(doc, name="Copy"):
    """Create a new Copy Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    CopyProxy(obj)
    if FreeCAD.GuiUp:
        CopyViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
