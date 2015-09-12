# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import
from nextgisweb.resource import Widget
from .model import QgisVectorStyle


class Widget(Widget):
    resource = QgisVectorStyle
    operation = ('create', 'update')
    amdmod = 'ngw-qgis/VectorStyleWidget'


def setup_pyramid(comp, config):
    pass
