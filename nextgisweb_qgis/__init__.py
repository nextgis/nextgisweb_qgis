# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

import os
import re
import PIL

from threading import Thread
from Queue import Queue
from StringIO import StringIO

from qgis.core import (
    QgsApplication,
    QgsMapLayerRegistry,
    QgsMapRendererCustomPainterJob,
    QgsVectorLayer,
    QgsMapSettings,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsLegendRenderer,
    QgsLayerTreeGroup,
    QgsLayerTreeModel,
    QgsLegendSettings)

from PyQt4.QtGui import (
    QImage,
    QPainter,
    QColor,
    qRgba)

from PyQt4.QtCore import (
    QSize,
    QSizeF,
    QByteArray,
    QBuffer,
    QIODevice)

from nextgisweb.component import Component
from .model import (
    Base,
    ImageOptions,
    LegendOptions)


class QgisComponent(Component):
    identity = 'qgis'
    metadata = Base.metadata

    def initialize(self):
        super(QgisComponent, self).initialize()

        if 'path' not in self.settings:
            self.settings['path'] = '/usr'
        if 'render_timeout' not in self.settings:
            self.settings['render_timeout'] = 10

        if 'svgpaths' in self.settings:
            self.settings['svgpaths'] = re.split(
                r'[,\s]+', self.settings.get('svgpaths', ''))
        else:
            self.settings['svgpaths'] = []

    def configure(self):
        super(QgisComponent, self).configure()

    def setup_pyramid(self, config):
        super(QgisComponent, self).setup_pyramid(config)

        # Separate thread for rendering,
        # will segfault otherwise with concurrent requests.
        self.queue = Queue()
        self.worker = Thread(target=self.renderer)
        self.worker.daemon = True
        self.worker.start()

        from . import view, api
        api.setup_pyramid(self, config)
        view.setup_pyramid(self, config)

    def renderer(self):
        if 'QGIS_AUTH_DB_DIR_PATH' not in os.environ:
            os.environ['QGIS_AUTH_DB_DIR_PATH'] = '/tmp'

        qgis = QgsApplication([], False)
        qgis.setPrefixPath(self.settings.get('path'), True)
        qgis.setDefaultSvgPaths(
            qgis.svgPaths() + self.settings.get('svgpaths'))
        qgis.setMaxThreads(1)
        qgis.initQgis()

        while True:
            options = self.queue.get()
            try:
                if isinstance(options, LegendOptions):
                    qml_filename, geometry_type, layer_name, result = options

                    # Make an empty memory layer and load qml
                    layer = QgsVectorLayer(geometry_type, layer_name, 'memory')
                    layer.loadNamedStyle(qml_filename)

                    QgsMapLayerRegistry.instance().addMapLayer(layer)

                    root = QgsLayerTreeGroup()
                    root.addLayer(layer)

                    # 'Cannot create a QPixmap when no GUI is being used'
                    #  warning occurs here
                    model = QgsLayerTreeModel(root)

                    settings = QgsLegendSettings()
                    settings.setTitle('')
                    settings.setBoxSpace(1)
                    settings.setSymbolSize(QSizeF(5, 3))
                    settings.setDpi(96)

                    renderer = QgsLegendRenderer(model, settings)

                    # Dots per mm
                    dpmm = settings.dpi() / 25.4

                    min_size = renderer.minimumSize()
                    size = QSize(dpmm * min_size.width(),
                                 dpmm * min_size.height())
                    img = QImage(size, QImage.Format_ARGB32)
                    img.fill(QColor(0, 0, 0, 0))

                    painter = QPainter()
                    painter.begin(img)
                    painter.scale(dpmm, dpmm)
                    renderer.drawLegend(painter)
                    painter.end()

                    QgsMapLayerRegistry.instance().removeAllMapLayers()

                    ba = QByteArray()
                    bf = QBuffer(ba)
                    bf.open(QIODevice.WriteOnly)
                    img.save(bf, 'PNG')
                    bf.close()

                    buf = StringIO()
                    buf.write(bf.data())
                    buf.seek(0)
                    result.put(buf)

                elif isinstance(options, ImageOptions):
                    fndata, srs, render_size, extended, \
                        target_box, result = options

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

                    # Create QImage by hand to be able to use
                    # QgsMapRendererCustomPainterJob. Others will not
                    # allow to workaround a bug with overlay rendering.
                    img = QImage(settings.outputSize(), QImage.Format_ARGB32)

                    # These cludges are needed for rendering
                    # on transparent background, otherwise it's a mess.
                    img.fill(QColor.fromRgba(qRgba(255, 255, 255, 255)))
                    img.fill(QColor.fromRgba(qRgba(255, 255, 255, 0)))

                    # DPI should be equal to settings, otherwise an error. In QImage
                    # the resolution is set in dots per meter for each axis.
                    dpm = settings.outputDpi() / 25.4 * 1000
                    img.setDotsPerMeterX(dpm)
                    img.setDotsPerMeterY(dpm)

                    painter = QPainter(img)
                    job = QgsMapRendererCustomPainterJob(settings, painter)
                    job.renderSynchronously()
                    painter.end()

                    QgsMapLayerRegistry.instance().removeAllMapLayers()

                    # Transform QImage to PIL
                    ba = QByteArray()
                    bf = QBuffer(ba)
                    bf.open(QIODevice.WriteOnly)
                    img.save(bf, 'PNG')
                    bf.close()

                    buf = StringIO()
                    buf.write(bf.data())
                    buf.seek(0)

                    img = PIL.Image.open(buf)

                    # Clip needed part
                    result.put(img.crop(target_box))

            except Exception as e:
                self.logger.error(e.message)

        qgis.exitQgis()

    settings_info = (
        dict(key='path', desc=u'QGIS installation folder'),
        dict(key='svgpaths', desc=u'SVG search folders'),
        dict(key='render_timeout', desc=u'QGIS rendering timeout for one request'),
    )


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis"))


def amd_packages():
    return ((
        'ngw-qgis', 'nextgisweb_qgis:amd/ngw-qgis'
    ),)
