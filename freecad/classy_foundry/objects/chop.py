"""Chop Document Object: applies a uniform cell-count chop to all axes of a source cb entity."""

import FreeCAD

from .recording import (
    SOLID_ATTRS, ProxyBase, ViewProviderBase, modifier_root_from, resolve_solid, solid_preview_shape,
)


class ChopProxy(ProxyBase):
    IS_MODIFIER = True

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty("App::PropertyLink", "Source", "ClassyFoundry", "Object to chop")
        obj.addProperty(
            "App::PropertyInteger", "Count", "Chop", "Number of cells along each axis"
        ).Count = 10

    def execute(self, obj):
        source = obj.Source
        if source is None:
            return

        attr, original = resolve_solid(source)
        if original is None:
            return

        chopped = original.copy()
        count = obj.Count
        for axis in range(3):
            chopped.chop(axis, count=count)

        for a in SOLID_ATTRS:
            if a != attr and hasattr(self, a):
                delattr(self, a)
        setattr(self, attr, chopped)
        obj.Shape = solid_preview_shape(chopped)

    def to_lines(self, obj):
        root = modifier_root_from(obj.Source)
        if root is None:
            return []
        varname = root.Name.lower()
        count = obj.Count
        return [f"{varname}.chop({axis}, count={count})" for axis in range(3)]


class ChopViewProvider(ViewProviderBase):
    pass


def make_chop(doc, name="Chop"):
    """Create a new Chop Document Object in `doc`."""
    obj = doc.addObject("Part::FeaturePython", name)
    ChopProxy(obj)
    if FreeCAD.GuiUp:
        ChopViewProvider(obj.ViewObject)
    doc.recompute()
    return obj
