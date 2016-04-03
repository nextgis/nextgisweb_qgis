# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import
import os
import os.path
from shutil import copyfileobj
from tempfile import mkdtemp
from Queue import Queue

import geojson
from zope.interface import implements

from nextgisweb import db
from nextgisweb.models import declarative_base
from nextgisweb.env import env
from nextgisweb.resource import (
    Resource,
    ResourceScope,
    DataScope,
    Serializer,
    SerializedProperty)
from nextgisweb.feature_layer import IFeatureLayer
from nextgisweb.render import (
    IRenderableStyle,
    IExtentRenderRequest,
    ITileRenderRequest)
from nextgisweb.file_storage import FileObj
from nextgisweb.geometry import box

Base = declarative_base()


class QgisVectorStyle(Base, Resource):
    identity = 'qgis_vector_style'
    cls_display_name = "QGIS vector style"

    implements(IRenderableStyle)

    __scope__ = DataScope

    qml_fileobj_id = db.Column(db.ForeignKey(FileObj.id), nullable=True)
    qml_fileobj = db.relationship(FileObj, cascade='all')

    @classmethod
    def check_parent(cls, parent):
        return IFeatureLayer.providedBy(parent)

    @property
    def feature_layer(self):
        return self.parent

    @property
    def srs(self):
        return self.parent.srs

    def render_request(self, srs):
        return RenderRequest(self, srs)

    def _render_image(self, srs, extent, size, padding=0):
        res_x = (extent[2] - extent[0]) / size[0]
        res_y = (extent[3] - extent[1]) / size[1]

        # Экстент с учетом отступов
        extended = (
            max(srs.minx, extent[0] - res_x * padding),
            max(srs.miny, extent[1] - res_y * padding),
            min(srs.maxx, extent[2] + res_x * padding),
            min(srs.maxy, extent[3] + res_y * padding),
        )

        # Маска отступов
        pmask = (
            extended[0] != srs.minx,
            extended[1] != srs.miny,
            extended[2] != srs.maxx,
            extended[3] != srs.maxy
        )

        # Размер изображения с учетом отступов
        render_size = (
            size[0] + int(pmask[0] + pmask[2]) * padding,
            size[1] + int(pmask[1] + pmask[3]) * padding
        )

        # Фрагмент изображения размера size
        target_box = (
            pmask[0] * padding,
            pmask[3] * padding,
            size[0] + pmask[0] * padding,
            size[1] + pmask[3] * padding
        )

        # Выбираем объекты по экстенту
        feature_query = self.parent.feature_query()

        # FIXME: Тоже самое, но через интерфейсы
        if hasattr(feature_query, 'srs'):
            feature_query.srs(srs)

        feature_query.intersects(box(*extended, srid=srs.id))
        feature_query.geom()
        features = feature_query()

        res_img = None
        try:
            dirname, fndata, fnstyle = None, None, None

            dirname = mkdtemp()
            fndata = os.path.join(dirname, 'layer.geojson')

            with open(fndata, 'wb') as fd:
                fd.write(geojson.dumps(features))

            fnstyle = os.path.join(dirname, 'layer.qml')
            os.symlink(env.file_storage.filename(self.qml_fileobj), fnstyle)

            result = Queue()
            env.qgis.queue.put((fndata, self.srs, render_size,
                                extended, target_box, result))
            render_timeout = int(env.qgis.settings.get('render_timeout'))
            res_img = result.get(block=True, timeout=render_timeout)

        finally:
            if fndata and os.path.isfile(fndata):
                os.unlink(fndata)
            if fnstyle and os.path.isfile(fnstyle):
                os.unlink(fnstyle)
            if dirname and os.path.isdir(dirname):
                os.rmdir(dirname)

        return res_img


class RenderRequest(object):
    implements(IExtentRenderRequest, ITileRenderRequest)

    def __init__(self, style, srs):
        self.style = style
        self.srs = srs

    def render_extent(self, extent, size):
        return self.style._render_image(self.srs, extent, size)

    def render_tile(self, tile, size):
        extent = self.srs.tile_extent(tile)
        return self.style._render_image(
            self.srs, extent, (size, size),
            padding=size / 2
        )


class _file_upload_attr(SerializedProperty):  # NOQA

    def setter(self, srlzr, value):
        srcfile, _ = env.file_upload.get_filename(value['id'])
        fileobj = env.file_storage.fileobj(component='qgis')
        srlzr.obj.qml_fileobj = fileobj
        dstfile = env.file_storage.filename(fileobj, makedirs=True)

        with open(srcfile, 'r') as fs, open(dstfile, 'w') as fd:
            copyfileobj(fs, fd)


class QgisVectorStyleSerializer(Serializer):
    identity = QgisVectorStyle.identity
    resclass = QgisVectorStyle

    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)
