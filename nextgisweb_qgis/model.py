# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import
from uuid import uuid4
from shutil import copyfileobj
from contextlib import contextmanager

from zope.interface import implementer
from osgeo import gdal, ogr, osr
import qgis_headless

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
    FIELD_TYPE as FIELD_TYPE,
    FIELD_TYPE_OGR as FIELD_OGR,
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
from nextgisweb.compat import lru_cache

from .util import _, qgis_init, qgis_image_to_pil


_FIELD_TYPE_TO_OGR = dict(zip(FIELD_TYPE.enum, FIELD_OGR))

Base = declarative_base()


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


@implementer(IRenderableStyle)
class QgisRasterStyle(Base, Resource):
    identity = 'qgis_raster_style'
    cls_display_name = _("QGIS style")

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

        # We need raster pyramids so use working directory filename
        # instead of original filename.
        # path = env.raster_layer.workdir_filename(self.parent.fileobj)

        raise NotImplementedError()


@implementer((IRenderableStyle, ILegendableStyle))
class QgisVectorStyle(Base, Resource):
    identity = 'qgis_vector_style'
    cls_display_name = _("QGIS style")

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

        feature_query = self.parent.feature_query()

        # Apply filter condition
        if cond is not None:
            feature_query.filter_by(**cond)

        # TODO: Do this via interfaces
        if hasattr(feature_query, 'srs'):
            feature_query.srs(srs)

        feature_query.intersects(box(*extended, srid=srs.id))
        feature_query.geom()
        features = feature_query()

        qml = _qml_cache(env.file_storage.filename(self.qml_fileobj))

        qgis_init()
        with _features_to_ogr(self.parent, features) as ogr_path:
            img = qgis_image_to_pil(qgis_headless.renderVector(
                ogr_path, qml, *(tuple(extent) + tuple(size) + (srs.id, 100))))

        return img

    def render_legend(self):
        raise NotImplementedError()


@on_data_change_feature_layer.connect
def on_data_change_feature_layer(resource, geom):
    for child in resource.children:
        if isinstance(child, QgisVectorStyle):
            on_data_change_renderable.fire(child, geom)


@implementer(IExtentRenderRequest, ITileRenderRequest)
class RenderRequest(object):

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


@contextmanager
def _features_to_ogr(src_layer, features):
    path = '/vsimem/{}.gpkg'.format(uuid4())
    ds = ogr.GetDriverByName('GPKG').CreateDataSource(path, options=[
        'ADD_GPKG_OGR_CONTENTS=NO', ])
    assert ds is not None, gdal.GetLastErrorMsg()

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(src_layer.srs.id)

    layer = ds.CreateLayer('', srs=srs, options=['SPATIAL_INDEX=NO', ])
    assert layer is not None, gdal.GetLastErrorMsg()

    defn = layer.GetLayerDefn()

    layer.CreateFields([
        ogr.FieldDefn(field.keyname, _FIELD_TYPE_TO_OGR[field.datatype])
        for field in src_layer.fields])

    for src_feat in features:
        feat = ogr.Feature(defn)
        feat.SetFID(src_feat.id)
        feat.SetGeometry(ogr.CreateGeometryFromWkb(src_feat.geom.wkb))

        for field in src_feat.fields:
            feat[field] = src_feat.fields[field]

        layer.CreateFeature(feat)

    try:
        yield path
    finally:
        del ds, layer, defn
        gdal.Unlink(path)


@lru_cache()
def _qml_cache(fn):
    with open(fn, 'r') as fd:
        return fd.read()
