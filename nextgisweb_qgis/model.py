# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

from collections import namedtuple
from shutil import copyfileobj

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
from nextgisweb.feature_layer import (
    IFeatureLayer,
    on_data_change as on_data_change_feature_layer,
)
from nextgisweb.render import (
    IRenderableStyle,
    IExtentRenderRequest,
    ITileRenderRequest,
    ILegendableStyle,
    on_style_change,
    on_data_change as on_data_change_renderable,
)
from nextgisweb.file_storage import FileObj
from nextgisweb.geometry import box

from .util import _

Base = declarative_base()

VectorRenderOptions = namedtuple('VectorRenderOptions', [
    'style', 'features', 'render_size',
    'extended', 'target_box'])

RasterRenderOptions = namedtuple('RasterRenderOptions', [
    'style', 'path', 'render_size',
    'extended', 'target_box'])

LegendOptions = namedtuple('LegendOptions', ['style', ])


def _render_bounds(extent, size, padding):
    res_x = (extent[2] - extent[0]) / size[0]
    res_y = (extent[3] - extent[1]) / size[1]

    # Bounding box with padding
    extended = (
        extent[0] - res_x * padding,
        extent[1] - res_y * padding,
        extent[2] + res_x * padding,
        extent[3] + res_y * padding,
    )

    # Image dimensions
    render_size = (
        size[0] + 2 * padding,
        size[1] + 2 * padding
    )

    # Crop box
    target_box = (
        padding,
        padding,
        size[0] + padding,
        size[1] + padding
    )

    return extended, render_size, target_box


class QgisRasterStyle(Base, Resource):
    identity = 'qgis_raster_style'
    cls_display_name = _("QGIS style")

    implements(IRenderableStyle)

    __scope__ = DataScope

    qml_fileobj_id = db.Column(db.ForeignKey(FileObj.id), nullable=True)
    qml_fileobj = db.relationship(FileObj, cascade='all')

    @classmethod
    def check_parent(cls, parent):
        return parent.cls == 'raster_layer'

    @property
    def srs(self):
        return self.parent.srs

    def render_request(self, srs):
        return RenderRequest(self, srs)

    def _render_image(self, srs, extent, size, cond=None, padding=0):
        extended, render_size, target_box = _render_bounds(
            extent, size, padding)

        path = env.file_storage.filename(self.parent.fileobj)

        options = RasterRenderOptions(
            self, path, render_size,
            extended, target_box)
        return env.qgis.renderer_job(options)


class QgisVectorStyle(Base, Resource):
    identity = 'qgis_vector_style'
    cls_display_name = _("QGIS style")

    implements(IRenderableStyle, ILegendableStyle)

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

    def render_request(self, srs, cond=None):
        return RenderRequest(self, srs, cond)

    def _render_image(self, srs, extent, size, cond, padding=0):
        extended, render_size, target_box = _render_bounds(
            extent, size, padding)

        # Выбираем объекты по экстенту
        feature_query = self.parent.feature_query()

        # Отфильтровываем объекты по условию
        if cond is not None:
            feature_query.filter_by(**cond)

        # FIXME: Тоже самое, но через интерфейсы
        if hasattr(feature_query, 'srs'):
            feature_query.srs(srs)

        feature_query.intersects(box(*extended, srid=srs.id))
        feature_query.geom()
        features = feature_query()

        options = VectorRenderOptions(
            self, features, render_size,
            extended, target_box)
        return env.qgis.renderer_job(options)

    def render_legend(self):
        options = LegendOptions(self)
        return env.qgis.renderer_job(options)


@on_data_change_feature_layer.connect
def on_data_change_feature_layer(resource, geom):
    for child in resource.children:
        if isinstance(child, QgisVectorStyle):
            on_data_change_renderable.fire(child, geom)


class RenderRequest(object):
    implements(IExtentRenderRequest, ITileRenderRequest)

    def __init__(self, style, srs, cond=None):
        self.style = style
        self.srs = srs
        self.cond = cond

    def render_extent(self, extent, size):
        return self.style._render_image(self.srs, extent, size, self.cond)

    def render_tile(self, tile, size):
        extent = self.srs.tile_extent(tile)
        return self.style._render_image(
            self.srs, extent, (size, size),
            self.cond,
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

        on_style_change.fire(srlzr.obj)


class QgisVectorStyleSerializer(Serializer):
    identity = QgisVectorStyle.identity
    resclass = QgisVectorStyle

    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)


class QgisRasterSerializer(Serializer):
    identity = QgisRasterStyle.identity
    resclass = QgisRasterStyle

    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)
