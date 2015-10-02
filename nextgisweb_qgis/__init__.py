# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import
from threading import Thread
from Queue import Queue
from qgis.core import (
    QgsApplication,
    QgsMapLayerRegistry,
    QgsMapRendererCustomPainterJob)
from PyQt4.QtGui import (QImage, QPainter, QColor, qRgba)

from nextgisweb.component import Component
from .model import Base


@Component.registry.register
class QgisComponent(Component):
    identity = 'qgis'
    metadata = Base.metadata

    def configure(self):
        super(QgisComponent, self).configure()

    def setup_pyramid(self, config):
        super(QgisComponent, self).setup_pyramid(config)

        # Отдельный поток в котором мы будем запускать весь рендеринг,
        # иначе все падает в segfault при конкурентной обработке запросов.
        self.queue = Queue()
        self.worker = Thread(target=self.renderer)
        self.worker.daemon = True
        self.worker.start()

        from . import view
        view.setup_pyramid(self, config)

    def renderer(self):
        QgsApplication.setPrefixPath('/usr', True)
        QgsApplication.setMaxThreads(1)
        QgsApplication.initQgis()
        qgis = QgsApplication([], False)

        while True:
            layer, settings, result = self.queue.get()

            QgsMapLayerRegistry.instance().addMapLayer(layer)
            settings.setLayers([layer.id()])

            # Создаем QImage руками чтобы можно было использовать
            # QgsMapRendererCustomPainterJob. Остальные не позволяют
            # обойти баг с рисованием поверх старого.
            img = QImage(settings.outputSize(), QImage.Format_ARGB32)

            # Эти костыли нужны для того, чтобы корректно рисовались
            # слои на прозрачном фоне, без этого получается каша.
            img.fill(QColor.fromRgba(qRgba(255, 255, 255, 255)))
            img.fill(QColor.fromRgba(qRgba(255, 255, 255, 0)))

            # DPI должно быть таким же как в settings, иначе ошибка. В QImage
            # разрешение указывается в точках на метр по каждой оси.
            dpm = settings.outputDpi() / 25.4 * 1000
            img.setDotsPerMeterX(dpm)
            img.setDotsPerMeterY(dpm)

            painter = QPainter(img)
            job = QgsMapRendererCustomPainterJob(settings, painter)
            job.renderSynchronously()
            painter.end()

            QgsMapLayerRegistry.instance().removeAllMapLayers()

            result.put(img)

        qgis.exitQgis()


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis"))


def amd_packages():
    return ((
        'ngw-qgis', 'nextgisweb_qgis:amd/ngw-qgis'
    ),)
