from nextgisweb.resource import Widget, Resource
import nextgisweb.dynmenu as dm

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
    # Расширения меню слоя
    class LayerMenuExt(dm.DynItem):
        def build(self, args):
            if isinstance(args.obj, (QgisVectorStyle, QgisRasterStyle)):
                yield dm.Label("qgis_style", _(u"QGIS style"))
                yield dm.Link(
                    "qgis_style/qml",
                    _(u"QML file"),
                    lambda args: args.request.route_url(
                        "qgis.style_qml", id=args.obj.id
                    ),
                )

    Resource.__dynmenu__.add(LayerMenuExt())
