# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

from nextgisweb.resource import Widget, Resource
import nextgisweb.dynmenu as dm

from .model import QgisVectorStyle
from .util import _


class Widget(Widget):
    resource = QgisVectorStyle
    operation = ('create', 'update')
    amdmod = 'ngw-qgis/VectorStyleWidget'


def setup_pyramid(comp, config):
    # Расширения меню слоя
    class LayerMenuExt(dm.DynItem):

        def build(self, args):
            if isinstance(args.obj, QgisVectorStyle):
                yield dm.Label('qgis_vector_style', _(u"QGIS style"))

                if args.obj.qml_fileobj is not None:
                    yield dm.Link(
                        'qgis_vector_style/qml', _(u"QML file"),
                        lambda args: args.request.route_url(
                            "qgis.vector_style_qml", id=args.obj.id))

    Resource.__dynmenu__.add(LayerMenuExt())
