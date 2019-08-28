# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

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
                yield dm.Label('qgis_style', _(u"QGIS style"))

                if (
                    args.obj.qml_fileobj is not None and
                    isinstance(args.obj, QgisVectorStyle)
                ):
                    yield dm.Link(
                        'qgis_vector_style/qml', _(u"QML file"),
                        lambda args: args.request.route_url(
                            "qgis.vector_style_qml", id=args.obj.id))

                if (
                    args.obj.qml_fileobj is not None and
                    isinstance(args.obj, QgisRasterStyle)
                ):
                    yield dm.Link(
                        'qgis_raster_style/qml', _(u"QML file"),
                        lambda args: args.request.route_url(
                            "qgis.raster_style_qml", id=args.obj.id))

    Resource.__dynmenu__.add(LayerMenuExt())
