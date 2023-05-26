from nextgisweb.lib import dynmenu as dm
from nextgisweb.resource import Widget, Resource

from .model import QgisVectorStyle, QgisRasterStyle
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

    def default_style_applicable(res):
        return comp.options['default_style'] and len(res.children) == 0 and (
            QgisRasterStyle.check_parent(res) or
            QgisVectorStyle.check_parent(res)
        )

    Resource.__psection__.register(
        key='qgis_default_style', priority=40,
        template='nextgisweb_qgis:template/default_style.mako',
        is_applicable=default_style_applicable)
