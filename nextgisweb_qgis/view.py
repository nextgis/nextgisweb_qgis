from nextgisweb.env import gettext
from nextgisweb.lib import dynmenu as dm

from nextgisweb.jsrealm import jsentry
from nextgisweb.resource import Resource, Widget
from nextgisweb.resource.view import resource_sections

from .model import QgisRasterStyle, QgisVectorStyle


class VectorStyleWidget(Widget):
    resource = QgisVectorStyle
    operation = ("create", "update")
    amdmod = jsentry("@nextgisweb/qgis/vector-editor-widget")

    def config(self):
        result = super().config()
        result["geometryType"] = self.obj.parent.geometry_type
        return result


class RasterStyleWidget(Widget):
    resource = QgisRasterStyle
    operation = ("create", "update")
    amdmod = jsentry("@nextgisweb/qgis/raster-editor-widget")

    def config(self):
        result = super().config()
        parent = self.obj.parent
        result["dtype"] = parent.dtype
        result["band_count"] = parent.band_count
        result["parent_id"] = parent.id
        return result


DEFAULT_STYLE_WIDGET_JSENTRY = jsentry("@nextgisweb/qgis/default-style-widget")


def setup_pyramid(comp, config):
    class LayerMenuExt(dm.DynItem):
        def build(self, args):
            if isinstance(args.obj, (QgisVectorStyle, QgisRasterStyle)):
                yield dm.Label("qgis_style", gettext("QGIS style"))
                yield dm.Link(
                    "qgis_style/qml",
                    gettext("QML file"),
                    lambda args: args.request.route_url("qgis.style_qml", id=args.obj.id),
                )

    Resource.__dynmenu__.add(LayerMenuExt())

    @resource_sections(priority=40)
    def resource_section_default_style(obj):
        if comp.options["default_style"] and len(obj.children) == 0:
            for cls in (QgisVectorStyle, QgisRasterStyle):
                if cls.check_parent(obj):
                    return dict(cls=cls.identity)
