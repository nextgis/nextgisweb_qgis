# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import
from threading import RLock
from qgis.core import QgsApplication

from nextgisweb.component import Component
from .model import Base


@Component.registry.register
class QgisComponent(Component):
    identity = 'qgis'
    metadata = Base.metadata

    def configure(self):
        super(QgisComponent, self).configure()
        QgsApplication.setPrefixPath('/usr', True)
        QgsApplication.initQgis()

        # Судя по API только один Qgis может быть запущен внутри одного
        # процесса, так что нам нужна блокировка, которая предотвратит
        # параллельное использование Qgis из разных потоков. Из одного все
        # должно быть ОК, поэтому RLock.

        self.rlock = RLock()

    def setup_pyramid(self, config):
        super(QgisComponent, self).setup_pyramid(config)
        from . import view
        view.setup_pyramid(self, config)


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis"))


def amd_packages():
    return ((
        'ngw-qgis', 'nextgisweb_qgis:amd/ngw-qgis'
    ),)
