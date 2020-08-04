# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

import qgis_headless

from nextgisweb.lib.config import Option, OptionAnnotations
from nextgisweb.component import Component

from .model import Base


class QgisComponent(Component):
    identity = 'qgis'
    metadata = Base.metadata

    def initialize(self):
        super(QgisComponent, self).initialize()

    def configure(self):
        super(QgisComponent, self).configure()
        qgis_headless.init([])

    def setup_pyramid(self, config):
        super(QgisComponent, self).setup_pyramid(config)

        from . import view, api
        api.setup_pyramid(self, config)
        view.setup_pyramid(self, config)

    option_annotations = OptionAnnotations((
        Option('svgpaths', list, default=[],
               doc="Search paths for SVG icons."),
    ))


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis"))


def amd_packages():
    return ((
        'ngw-qgis', 'nextgisweb_qgis:amd/ngw-qgis'
    ),)
