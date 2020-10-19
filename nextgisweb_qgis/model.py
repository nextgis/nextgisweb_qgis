# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import
import logging
from uuid import uuid4
from shutil import copyfileobj
from contextlib import contextmanager
from io import BytesIO
from six import ensure_str

from zope.interface import implementer
from osgeo import gdal, ogr, osr
from qgis_headless import MapRequest, CRS, Layer, Style
from PIL import Image

from nextgisweb import db
from nextgisweb.models import declarative_base
from nextgisweb.env import env
from nextgisweb.resource import (
    Resource,
    ResourceScope,
    DataScope,
    DataStructureScope,
    Serializer,
    SerializedProperty as SP,
    SerializedResourceRelationship as SRR,
)
from nextgisweb.feature_layer import (
    IFeatureLayer,
    IFeatureQuerySimplify,
    FIELD_TYPE as FIELD_TYPE,
    FIELD_TYPE_OGR as FIELD_OGR,
    GEOM_TYPE as GEOM_TYPE,
    on_data_change as on_data_change_feature_layer,
)
from nextgisweb.svg_marker_library import SVGMarkerLibrary
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

from .util import _, qgis_image_to_pil


_GEOM_TYPE_TO_QGIS = {
    GEOM_TYPE.POINT: Layer.GT_POINT,
    GEOM_TYPE.LINESTRING: Layer.GT_LINESTRING,
    GEOM_TYPE.POLYGON: Layer.GT_POLYGON,
    GEOM_TYPE.MULTIPOINT: Layer.GT_MULTIPOINT,
    GEOM_TYPE.MULTILINESTRING: Layer.GT_MULTILINESTRING,
    GEOM_TYPE.MULTIPOLYGON: Layer.GT_MULTIPOLYGON,
    GEOM_TYPE.POINTZ: Layer.GT_POINTZ,
    GEOM_TYPE.LINESTRINGZ: Layer.GT_LINESTRINGZ,
    GEOM_TYPE.POLYGONZ: Layer.GT_POLYGONZ,
    GEOM_TYPE.MULTIPOINTZ: Layer.GT_MULTIPOINTZ,
    GEOM_TYPE.MULTILINESTRINGZ: Layer.GT_MULTILINESTRINGZ,
    GEOM_TYPE.MULTIPOLYGONZ: Layer.GT_MULTIPOLYGONZ,
}

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
        gdal_path = env.raster_layer.workdir_filename(self.parent.fileobj)

        env.qgis.qgis_init()

        mreq = MapRequest()
        mreq.set_dpi(96)
        mreq.set_crs(CRS.from_epsg(srs.id))

        style = Style.from_string(_qml_cache(
            env.file_storage.filename(self.qml_fileobj)))

        layer = Layer.from_gdal(gdal_path)
        mreq.add_layer(layer, style)

        res = mreq.render_image(extent, size)
        img = qgis_image_to_pil(res)

        return img


@implementer((IRenderableStyle, ILegendableStyle))
class QgisVectorStyle(Base, Resource):
    identity = 'qgis_vector_style'
    cls_display_name = _("QGIS style")

    __scope__ = (DataScope, DataStructureScope)

    qml_fileobj_id = db.Column(db.ForeignKey(FileObj.id), nullable=True)
    svg_marker_library_id = db.Column(db.ForeignKey(SVGMarkerLibrary.id), nullable=True)

    qml_fileobj = db.relationship(FileObj, cascade='all')
    svg_marker_library = db.relationship(
        SVGMarkerLibrary, foreign_keys=svg_marker_library_id,
        cascade=False, cascade_backrefs=False,
    )

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

        fields = tuple([
            (field.keyname, ) + _FIELD_TYPE_TO_QGIS[field.datatype]
            for field in self.parent.fields
        ])

        features = list()
        for feat in feature_query():
            features.append((feat.id, feat.geom.wkb, tuple([
                convert(feat.fields[field])
                for field, _, convert in fields])))

        if len(features) == 0:
            return Image.new('RGBA', size)

        env.qgis.qgis_init()

        crs = CRS.from_epsg(srs.id)

        mreq = MapRequest()
        mreq.set_dpi(96)
        mreq.set_crs(crs)

        def path_resolver(name):
            candidates = [name, ]
            if name[-4:].lower() == '.svg':
                candidates.append(name[:-4])
            svg_symbol = self.svg_marker_library.find_svg_symbol(candidates)
            return name if svg_symbol is None else svg_symbol.path

        callback = None if self.svg_marker_library is None else path_resolver

        style = Style.from_string(_qml_cache(
            env.file_storage.filename(self.qml_fileobj)), callback)

        layer = Layer.from_data(
            _GEOM_TYPE_TO_QGIS[self.parent.geometry_type],
            crs, fields, tuple(features))

        mreq.add_layer(layer, style)

        res = mreq.render_image(extent, size)
        return qgis_image_to_pil(res)

    def render_legend(self):
        env.qgis.qgis_init()

        mreq = MapRequest()
        mreq.set_dpi(96)

        style = Style.from_string(_qml_cache(
            env.file_storage.filename(self.qml_fileobj)))

        layer = Layer.from_data(
            _GEOM_TYPE_TO_QGIS[self.parent.geometry_type],
            CRS.from_epsg(self.parent.srs.id), (), ())

        mreq.add_layer(layer, style)
        res = mreq.render_legend()
        img = qgis_image_to_pil(res)

        # PNG-compressed buffer is required for render_legend()
        # TODO: Switch to PIL Image in future!
        buf = BytesIO()
        img.save(buf, 'png')
        buf.seek(0)
        return buf


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


class _file_upload_attr(SP):  # NOQA

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
    svg_marker_library = SRR(read=DataStructureScope.read, write=DataStructureScope.write)


class QgisRasterSerializer(Serializer):
    identity = QgisRasterStyle.identity
    resclass = QgisRasterStyle

    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)


@lru_cache()
def _qml_cache(fn):
    with open(fn, 'r') as fd:
        return fd.read()


def _convert_none(v):
    return v


def _convert_date(v):
    if v is not None:
        return v.timetuple()[0:3]


def _convert_time(v):
    if v is not None:
        return (v.hour, v.minute, v.second)


def _convert_datetime(v):
    if v is not None:
        return v.timetuple()[0:6]


_FIELD_TYPE_TO_QGIS = {
    FIELD_TYPE.INTEGER: (Layer.FT_INTEGER, _convert_none),
    FIELD_TYPE.BIGINT: (Layer.FT_INTEGER64, _convert_none),
    FIELD_TYPE.REAL: (Layer.FT_REAL, _convert_none),
    FIELD_TYPE.STRING: (Layer.FT_STRING, _convert_none),
    FIELD_TYPE.DATE: (Layer.FT_DATE, _convert_date),
    FIELD_TYPE.TIME: (Layer.FT_TIME, _convert_time),
    FIELD_TYPE.DATETIME: (Layer.FT_DATETIME, _convert_datetime),
}
