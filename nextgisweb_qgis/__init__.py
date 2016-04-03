# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import
from threading import Thread
from Queue import Queue
from StringIO import StringIO
import PIL

from qgis.core import (
    QgsApplication,
    QgsMapLayerRegistry,
    QgsMapRendererCustomPainterJob,
    QgsVectorLayer,
    QgsMapSettings,
    QgsRectangle,
    QgsCoordinateReferenceSystem)

from PyQt4.QtGui import (
    QImage,
    QPainter,
    QColor,
    qRgba)

from PyQt4.QtCore import (
    QSize,
    QByteArray,
    QBuffer,
    QIODevice)

from nextgisweb.component import Component
from .model import Base


class QgisComponent(Component):
    identity = 'qgis'
    metadata = Base.metadata

    def initialize(self):
        super(QgisComponent, self).initialize()

        if 'path' not in self.settings:
            self.settings['path'] = '/usr'
        if 'render_timeout' not in self.settings:
            self.settings['render_timeout'] = 10

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
        qgis = QgsApplication([], False)
        qgis.setPrefixPath(self.settings.get('path'), True)
        qgis.setMaxThreads(1)
        qgis.initQgis()

        while True:
            try:
                fndata, srs, render_size, extended, \
                    target_box, result = self.queue.get()

                layer = QgsVectorLayer(fndata, 'layer', 'ogr')

                crs = QgsCoordinateReferenceSystem(srs.id)
                layer.setCrs(crs)

                settings = QgsMapSettings()
                settings.setLayers([layer.id()])
                settings.setFlag(QgsMapSettings.DrawLabeling)
                settings.setFlag(QgsMapSettings.Antialiasing)

                settings.setCrsTransformEnabled(True)
                settings.setDestinationCrs(crs)
                settings.setMapUnits(crs.mapUnits())
                settings.setOutputSize(QSize(*render_size))
                settings.setExtent(QgsRectangle(*extended))

                settings.setOutputImageFormat(QImage.Format_ARGB32)
                bgcolor = QColor.fromRgba(qRgba(255, 255, 255, 0))
                settings.setBackgroundColor(bgcolor)
                settings.setOutputDpi(96)

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

                # Преобразование QImage в PIL
                ba = QByteArray()
                bf = QBuffer(ba)
                bf.open(QIODevice.WriteOnly)
                img.save(bf, 'PNG')
                bf.close()

                buf = StringIO()
                buf.write(bf.data())
                buf.seek(0)

                img = PIL.Image.open(buf)
                img.crop(target_box)

                result.put(img)
            except Exception as ex:
                print(ex.message)
                # need write to log?

        qgis.exitQgis()

    settings_info = (
        dict(key='path', desc=u'Директория, в которую установлен QGIS'),
        dict(key='render_timeout', desc=u'Таймаут отрисовки одного запроса QGIS\'ом в cек' ),
    )


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis"))


def amd_packages():
    return ((
        'ngw-qgis', 'nextgisweb_qgis:amd/ngw-qgis'
    ),)
