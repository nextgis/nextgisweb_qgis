# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import
import sys
import os
import re
import PIL
from datetime import date, time, datetime, timedelta
from pkg_resources import resource_filename
import six

from threading import Thread
from Queue import Queue, Empty, Full
from StringIO import StringIO

from sqlalchemy.orm.exc import DetachedInstanceError

from qgis.core import (
    QGis,
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

from nextgisweb.lib.config import Option, OptionAnnotations
from nextgisweb.component import Component
from nextgisweb.core.exception import user_exception
from nextgisweb.feature_layer import FIELD_TYPE, GEOM_TYPE

from .model import Base, VectorRenderOptions, RasterRenderOptions, LegendOptions
from .util import _


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

    def sys_info(self):
        return (
            ("QGIS", QGis.QGIS_VERSION),
        )

    def renderer_job(self, options):
        result_queue = Queue(maxsize=1)
        self.queue.put((options, result_queue))

        timeout = self.options['render_timeout'].total_seconds()
        try:
            result = result_queue.get(block=True, timeout=timeout)
        except Empty as exc:
            try:
                result_queue.put_nowait(None)  # Just say cancel the job
            except Full:
                pass  # Race condition between timeout and putting a result

            raise user_exception(
                exc, http_status_code=503,
                title=_("QGIS render timeout"))

        if isinstance(result[0], Exception):
            six.reraise(*result[1])
        else:
            return result[0]

    def renderer(self):
        if 'QGIS_AUTH_DB_DIR_PATH' not in os.environ:
            os.environ['QGIS_AUTH_DB_DIR_PATH'] = '/tmp'

        qgis = None
        while True:
            options, result = self.queue.get()

            # Don't start QGIS until first request
            if qgis is None:
                qgis = QgsApplication([], False)
                qgis.setPrefixPath(self.options['prefix_path'], True)
                qgis.setDefaultSvgPaths(self.options['svgpaths'])
                qgis.setMaxThreads(1)
                qgis.initQgis()

            # Check was the job canceled
            if result.full():
                continue

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

                    try:
                        result.put((buf, ))
                    except Full:
                        pass # That's OK, job was canceled

                else:
                    features = None
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
                    cimg = img.crop(target_box)

                    try:
                        result.put((cimg, ))
                    except Full:
                        pass # That's OK, job was canceled

            except Exception as exc:
                if isinstance(exc, DetachedInstanceError) and result.full():
                    pass  # That's OK, database session may already closed
                else:
                    result.put((exc, sys.exc_info()))

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

    option_annotations = OptionAnnotations((
        Option('render_timeout', timedelta, default=timedelta(seconds=60),
               doc="Timeout for one rendering request."),

        Option('svgpaths', list, default=[resource_filename('nextgisweb', 'svg_marker_library/preset'), ],
               doc="Search paths for SVG icons."),

        Option('prefix_path', str, default="/usr",
               doc="QGIS installation prefix path."),
    ))


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis"))


def amd_packages():
    return ((
        'ngw-qgis', 'nextgisweb_qgis:amd/ngw-qgis'
    ),)
