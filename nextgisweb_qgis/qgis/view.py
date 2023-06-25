from nextgisweb.lib import dynmenu as dm

from nextgisweb.resource import Resource, Widget
from nextgisweb.resource.view import resource_sections

from .model import QgisRasterStyle, QgisVectorStyle
from .util import _


class VectorStyleWidget(Widget):
    resource = QgisVectorStyle
    operation = ('create', 'update')
    amdmod = 'ngw-qgis/VectorStyleWidget'


class RasterStyleWidget(Widget):
    resource = QgisRasterStyle
    operation = ('create', 'update')
    amdmod = 'ngw-qgis/RasterStyleWidget'


def setup_pyramid(comp, config):

    class LayerMenuExt(dm.DynItem):
        def build(self, args):
            if isinstance(args.obj, (QgisVectorStyle, QgisRasterStyle)):
                yield dm.Label("qgis_style", _("QGIS style"))
                yield dm.Link(
                    "qgis_style/qml",
                    _("QML file"),
                    lambda args: args.request.route_url(
                        "qgis.style_qml", id=args.obj.id
                    ),
                )

    Resource.__dynmenu__.add(LayerMenuExt())

    @resource_sections(priority=40, template='default_style.mako')
    def resource_section_default_style(obj):
        return comp.options['default_style'] and len(obj.children) == 0 and (
            QgisRasterStyle.check_parent(obj) or QgisVectorStyle.check_parent(obj)
        )
