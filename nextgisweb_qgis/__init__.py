# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

import os
import re
import PIL
from datetime import date, time, datetime

from threading import Thread
from Queue import Queue
from StringIO import StringIO

from osgeo import gdal
from qgis.core import (
    QgsApplication,
    QgsMapLayerRegistry,
    QgsMapRendererCustomPainterJob,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsMapSettings,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsLegendRenderer,
    QgsLayerTreeGroup,
    QgsLayerTreeModel,
    QgsLegendSettings,
    QgsFeature,
    QgsField,
    QgsGeometry)

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
    QVariant,
    QDate,
    QTime,
    QDateTime,
    QIODevice)

from nextgisweb.component import Component
from nextgisweb.feature_layer import FIELD_TYPE, GEOM_TYPE
from .model import (
    Base,
    VectorRenderOptions,
    RasterRenderOptions,
    LegendOptions)


# Convert field type to QGIS type
FIELD_TYPE_TO_QGIS = {
    FIELD_TYPE.INTEGER: (QVariant.Int, 'int4'),
    FIELD_TYPE.BIGINT: (QVariant.LongLong, 'int8'),
    FIELD_TYPE.REAL: (QVariant.Double, 'real'),
    FIELD_TYPE.STRING: (QVariant.String, 'string'),
    FIELD_TYPE.DATE: (QVariant.Date, 'date'),
    FIELD_TYPE.TIME: (QVariant.Time, 'time'),
    FIELD_TYPE.DATETIME: (QVariant.DateTime, 'datetime'),
}


class QgisComponent(Component):
    identity = 'qgis'
    metadata = Base.metadata

    def initialize(self):
        super(QgisComponent, self).initialize()

        if 'path' not in self.settings:
            self.settings['path'] = '/usr'

        if 'svgpaths' in self.settings:
            self.settings['svgpaths'] = re.split(
                r'[,\s]+', self.settings.get('svgpaths', ''))
        else:
            self.settings['svgpaths'] = []

        self._render_timeout = float(self.settings.get('render_timeout', '60'))

        # Separate thread for rendering,
        # will segfault otherwise with concurrent requests.
        self.queue = Queue()
        self.worker = Thread(target=self.renderer)
        self.worker.daemon = True
        self.worker.start()

    def configure(self):
        super(QgisComponent, self).configure()

    def setup_pyramid(self, config):
        super(QgisComponent, self).setup_pyramid(config)

        from . import view, api
        api.setup_pyramid(self, config)
        view.setup_pyramid(self, config)

    def renderer_job(self, options):
        result_queue = Queue()
        self.queue.put((options, result_queue))

        result = result_queue.get(block=True, timeout=self._render_timeout)

        if isinstance(result, Exception):
            raise result
        return result

    def renderer(self):
        if 'QGIS_AUTH_DB_DIR_PATH' not in os.environ:
            os.environ['QGIS_AUTH_DB_DIR_PATH'] = '/tmp'

        qgis = None
        while True:
            options, result = self.queue.get()

            # Don't start QGIS until first request
            if qgis is None:
                qgis = QgsApplication([], False)
                qgis.setPrefixPath(self.settings.get('path'), True)
                qgis.setDefaultSvgPaths(
                    qgis.svgPaths() + self.settings.get('svgpaths'))
                qgis.setMaxThreads(1)
                qgis.initQgis()

            try:
                if isinstance(options, LegendOptions):
                    style, = options

                    layer = self._qgs_memory_layer(style)
                    layer.setName(style.parent.display_name)

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

                else:
                    path = features = None
                    if isinstance(options, VectorRenderOptions):
                        style, features, render_size, \
                            extended, target_box = options
                        layer = self._qgs_memory_layer(style, features=features)
                    elif isinstance(options, RasterRenderOptions):
                        style, path, render_size, \
                            extended, target_box = options
                        layer = QgsRasterLayer(path)
                        layer.loadNamedStyle(self.env.file_storage.filename(
                            style.qml_fileobj))

                    settings = QgsMapSettings()
                    settings.setLayers([layer.id()])
                    settings.setFlag(QgsMapSettings.DrawLabeling)
                    settings.setFlag(QgsMapSettings.Antialiasing)

                    settings.setCrsTransformEnabled(True)
                    settings.setDestinationCrs(layer.crs())
                    settings.setMapUnits(layer.crs().mapUnits())
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

                    # DPI should be equal to settings, otherwise an error.
                    # In QImage the resolution is set in dots per meter
                    # for each axis.
                    dpm = settings.outputDpi() / 25.4 * 1000
                    img.setDotsPerMeterX(dpm)
                    img.setDotsPerMeterY(dpm)

                    painter = QPainter(img)
                    job = QgsMapRendererCustomPainterJob(settings, painter)
                    job.renderSynchronously()
                    painter.end()

                    QgsMapLayerRegistry.instance().removeAllMapLayers()

                    img = self._qimage_to_pil(img)

                    # Clip needed part
                    result.put(img.crop(target_box))

                    # Cleanup
                    if path is not None:
                        gdal.Unlink(path)

            except Exception as exc:
                self.logger.error(exc.message)
                result.put(exc)

        qgis.exitQgis()

    def _qgs_memory_layer(self, style, features=None):
        """ Create QgsVectorLayer with memory backend and load
        features into it """

        geometry_type = style.parent.geometry_type

        # QGIS memory layer doesn't support 3D geometry types
        if geometry_type in GEOM_TYPE.has_z:   
            # TODO: Remove enum values magic
            # Strip last Z character
            geometry_type = geometry_type[:-1] 

        result = QgsVectorLayer(geometry_type, None, 'memory')
        provider = result.dataProvider()

        # Setup layer fields
        fldmap = {}
        for fld in style.parent.fields:
            provider.addAttributes([QgsField(
                fld.keyname,
                *FIELD_TYPE_TO_QGIS[fld.datatype]
            )])
            fldmap[fld.keyname] = len(fldmap)
        qgsfields = provider.fields()
        result.updateFields()

        # Load style from qml file
        result.loadNamedStyle(self.env.file_storage.filename(
            style.qml_fileobj))

        # Disable read only flag when it was set via qml file
        result.setReadOnly(False)

        # Load features into layers if needed
        if features is not None:
            result.startEditing()

            for feat in features:
                qgsfeat = QgsFeature(qgsfields)
                fattrs = [None] * len(fldmap)
                for k, v in feat.fields.iteritems():
                    if v is None:
                        continue
                    elif isinstance(v, date):
                        v = QDate(v.year, v.month, v.day)
                    elif isinstance(v, time):
                        v = QTime(v.hour, v.minute, v.second)
                    elif isinstance(v, datetime):
                        v = QDateTime(
                            v.year, v.month, v.day,
                            v.hour, v.minute, v.second)
                    fattrs[fldmap[k]] = v
                qgsfeat.setAttributes(fattrs)

                # Method fromWkb() is much faster constructor fromWkt()
                # TODO: QGIS 3 have constructor fromWkb()
                qgsgeom = QgsGeometry()
                qgsgeom.fromWkb(feat.geom.wkb)
                qgsfeat.setGeometry(qgsgeom)

                result.addFeature(qgsfeat)

            result.commitChanges()

        result.setCrs(QgsCoordinateReferenceSystem(
            style.parent.srs.id))

        return result

    def _qimage_to_pil(self, qimage):
        """ Convert QImage to PIL Image """

        ba = QByteArray()
        bf = QBuffer(ba)
        bf.open(QIODevice.WriteOnly)
        qimage.save(bf, 'TIFF', quality=100)
        bf.close()

        buf = StringIO()
        buf.write(bf.data())
        buf.seek(0)

        return PIL.Image.open(buf)

    settings_info = (
        dict(key='path', desc=u'QGIS installation folder'),
        dict(key='svgpaths', desc=u'SVG search folders'),
        dict(key='render_timeout',
             desc=u'QGIS rendering timeout for one request'),
    )


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis"))


def amd_packages():
    return ((
        'ngw-qgis', 'nextgisweb_qgis:amd/ngw-qgis'
    ),)
