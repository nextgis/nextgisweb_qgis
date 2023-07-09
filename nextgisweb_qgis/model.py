import re
from io import BytesIO
from os.path import normpath
from os.path import sep as path_sep
from shutil import copyfile

from cachetools import LRUCache
from shapely.geometry import box
from sqlalchemy.orm import declared_attr
from zope.interface import implementer

from nextgisweb.env import COMP_ID, Base, _, env
from nextgisweb.lib import db
from nextgisweb.lib.geometry import Geometry

from nextgisweb.core.exception import OperationalError, ValidationError
from nextgisweb.feature_layer import FIELD_TYPE, GEOM_TYPE, IFeatureLayer
from nextgisweb.feature_layer import on_data_change as on_data_change_feature_layer
from nextgisweb.file_storage import FileObj
from nextgisweb.render import (
    IExtentRenderRequest,
    ILegendableStyle,
    ILegendSymbols,
    IRenderableStyle,
    ITileRenderRequest,
    LegendSymbol,
    on_style_change,
)
from nextgisweb.render import on_data_change as on_data_change_renderable
from nextgisweb.resource import (
    DataScope,
    DataStructureScope,
    Resource,
    ResourceScope,
    Serializer,
)
from nextgisweb.resource import SerializedProperty as SP
from nextgisweb.resource import SerializedResourceRelationship as SRR
from nextgisweb.svg_marker_library import SVGMarkerLibrary

from qgis_headless import (
    CRS,
    LT_RASTER,
    LT_VECTOR,
    Layer,
    MapRequest,
    Style,
    StyleTypeMismatch,
    StyleValidationError,
)
from qgis_headless.util import to_pil as qgis_image_to_pil

from .util import rand_color

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

STRIP_SVG_PATH = re.compile(
    r'^(/usr/share/qgis/svg/|/Users/[^/]+/|/home/[^/]+/|(../)+|/)',
    re.IGNORECASE)


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


class QgisStyleMixin:
    cls_display_name = _("QGIS style")

    @declared_attr
    def qml_fileobj_id(cls):
        return db.Column(db.ForeignKey(FileObj.id), nullable=True)

    @declared_attr
    def qml_fileobj(cls):
        return db.relationship(FileObj, cascade='all')

    @property
    def srs(self):
        return self.parent.srs

    def from_file(self, filename):
        self.qml_fileobj = env.file_storage.fileobj(COMP_ID)
        dstfile = env.file_storage.filename(self.qml_fileobj, makedirs=True)
        copyfile(filename, dstfile)
        return self


@implementer(IRenderableStyle)
class QgisRasterStyle(Base, QgisStyleMixin, Resource):
    identity = 'qgis_raster_style'

    __scope__ = DataScope

    @classmethod
    def check_parent(cls, parent):
        return parent.cls == 'raster_layer'

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

        style = read_style(self)

        layer = Layer.from_gdal(gdal_path)
        mreq.add_layer(layer, style)

        res = mreq.render_image(extent, size)
        img = qgis_image_to_pil(res)

        return img


def path_resolver_factory(svg_marker_library):

    def path_resolver(name):
        if name.startswith(('http://', 'https://', 'base64:')):
            return name

        name_library = normpath(name)
        name_library = STRIP_SVG_PATH.sub('', name_library)
        name_library = re.sub(r'\.svg$', '', name_library)

        # Some styles may contain empty SVG markers
        if name_library == "":
            return name

        items = name_library.split(path_sep)
        for i in range(len(items)):
            candidate = path_sep.join(items[i:])
            filename = env.svg_marker_library.lookup(candidate, svg_marker_library)
            if filename is not None:
                return filename

        return name

    return path_resolver


@implementer((IRenderableStyle, ILegendableStyle, ILegendSymbols))
class QgisVectorStyle(Base, QgisStyleMixin, Resource):
    identity = 'qgis_vector_style'

    __scope__ = (DataScope, DataStructureScope)

    svg_marker_library_id = db.Column(db.ForeignKey(SVGMarkerLibrary.id), nullable=True)
    svg_marker_library = db.relationship(
        SVGMarkerLibrary, foreign_keys=svg_marker_library_id,
        cascade=False, cascade_backrefs=False,
        # Backref is just for cleaning up QgisVectorStyle -> SVGMarkerLibrary
        # reference. SQLAlchemy does this automatically.
        backref=db.backref('_backref_qgis_vector_style'),
    )

    @classmethod
    def check_parent(cls, parent):
        return IFeatureLayer.providedBy(parent)

    @property
    def feature_layer(self):
        return self.parent

    def render_request(self, srs, cond=None):
        return RenderRequest(self, srs, cond)

    def _render_image(self, srs, extent, size, cond, padding=0):
        extended, render_size, target_box = _render_bounds(
            extent, size, padding)

        feature_query = self.parent.feature_query()

        # Apply filter condition
        if cond is not None:
            feature_query.filter_by(**cond)

        feature_query.srs(srs)

        bbox = Geometry.from_shape(box(*extended), srid=srs.id)
        feature_query.intersects(bbox)
        feature_query.geom()

        env.qgis.qgis_init()

        crs = CRS.from_epsg(srs.id)

        mreq = MapRequest()
        mreq.set_dpi(96)
        mreq.set_crs(crs)

        style = read_style(self)

        style_attrs = style.used_attributes()
        if style_attrs is not None:
            style_attrs = {attr.lower() for attr in style_attrs}

        qhl_fields = list()
        cnv_fields = list()
        qry_fields = list()

        for field in self.parent.fields:
            fkeyname = field.keyname
            if (style_attrs is not None) and (fkeyname.lower() not in style_attrs):
                continue
            field_to_qgis = _FIELD_TYPE_TO_QGIS[field.datatype]
            qhl_fields.append((fkeyname, field_to_qgis[0]))
            cnv_fields.append((fkeyname, field_to_qgis[1]))
            qry_fields.append(fkeyname)

        feature_query.fields(*qry_fields)

        features = list()
        for feat in feature_query():
            features.append((feat.id, feat.geom.wkb, tuple([
                convert(feat.fields[field])
                for field, convert in cnv_fields])))

        if len(features) == 0:
            return None

        layer = Layer.from_data(
            _GEOM_TYPE_TO_QGIS[self.parent.geometry_type],
            crs, tuple(qhl_fields), tuple(features))

        mreq.add_layer(layer, style)

        res = mreq.render_image(extent, size)
        return qgis_image_to_pil(res)

    def render_legend(self):
        env.qgis.qgis_init()

        mreq = MapRequest()
        mreq.set_dpi(96)

        style = read_style(self)

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

    def legend_symbols(self, icon_size):
        env.qgis.qgis_init()

        mreq = MapRequest()
        mreq.set_dpi(96)

        style = read_style(self)

        layer = Layer.from_data(
            _GEOM_TYPE_TO_QGIS[self.parent.geometry_type],
            CRS.from_epsg(self.parent.srs.id), (), ())

        mreq.add_layer(layer, style)

        return [
            LegendSymbol(
                display_name=s.title(),
                icon=qgis_image_to_pil(s.icon())
            ) for s in mreq.legend_symbols(0, (icon_size, icon_size))
        ]


DataScope.read.require(
    ResourceScope.read, cls=QgisVectorStyle,
    attr='svg_marker_library', attr_empty=True)


@on_data_change_feature_layer.connect
def on_data_change_feature_layer(resource, geom):
    for child in resource.children:
        if isinstance(child, QgisVectorStyle):
            on_data_change_renderable.fire(child, geom)


@implementer(IExtentRenderRequest, ITileRenderRequest)
class RenderRequest:

    def __init__(self, style, srs, cond=None):
        self.style = style
        self.srs = srs
        self.cond = cond

    def render_extent(self, extent, size):
        try:
            return self.style._render_image(self.srs, extent, size, self.cond)
        except Exception as exc:
            _reraise_qgis_exception(exc, OperationalError)

    def render_tile(self, tile, size):
        extent = self.srs.tile_extent(tile)
        try:
            return self.style._render_image(
                self.srs, extent, (size, size),
                self.cond,
                padding=size / 2
            )
        except Exception as exc:
            _reraise_qgis_exception(exc, OperationalError)


class _file_upload_attr(SP):  # NOQA

    def setter(self, srlzr, value):
        env.qgis.qgis_init()

        srcfile, meta = env.file_upload.get_filename(value['id'])

        params = dict()

        layer = srlzr.obj.parent
        if IFeatureLayer.providedBy(layer):
            params['layer_type'] = LT_VECTOR
            gt = layer.geometry_type
            gt_qgis = _GEOM_TYPE_TO_QGIS[gt]
            params['layer_geometry_type'] = gt_qgis
        else:
            params['layer_type'] = LT_RASTER

        try:
            Style.from_file(srcfile, **params)
        except Exception as exc:
            _reraise_qgis_exception(exc, ValidationError)

        fileobj = env.file_storage.fileobj(component=COMP_ID)
        srlzr.obj.qml_fileobj = fileobj
        dstfile = env.file_storage.filename(fileobj, makedirs=True)

        copyfile(srcfile, dstfile)

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


_style_cache = LRUCache(maxsize=256)


def read_style(qgis_style):
    if qgis_style.qml_fileobj_id is None:
        key = qgis_style.id

    else:
        uuid = qgis_style.qml_fileobj.uuid
        if isinstance(qgis_style, QgisVectorStyle):
            sml = qgis_style.svg_marker_library
            geometry_type = qgis_style.parent.geometry_type
        else:
            sml = geometry_type = None

        key = (uuid, None if sml is None else sml.tstamp, geometry_type)

    if (style := _style_cache.get(key)) is None:
        params = dict()

        if qgis_style.qml_fileobj_id is None:
            if isinstance(qgis_style, QgisVectorStyle):
                params['layer_type'] = LT_VECTOR
                params['layer_geometry_type'] = _GEOM_TYPE_TO_QGIS[qgis_style.parent.geometry_type]
                if params['layer_geometry_type'] in (
                    Layer.GT_POLYGON, Layer.GT_POLYGONZ,
                    Layer.GT_MULTIPOLYGON, Layer.GT_MULTIPOLYGONZ,
                ):
                    opacity = 63
                else:
                    opacity = 255
                params['color'] = rand_color(qgis_style.id) + (opacity, )
            else:
                params['layer_type'] = LT_RASTER
            style = Style.from_defaults(**params)

        else:
            # NOTE: Some file objects can have component != 'qgis'
            filename = env.file_storage.filename(qgis_style.qml_fileobj)
            if geometry_type is not None:
                params['layer_geometry_type'] = _GEOM_TYPE_TO_QGIS[geometry_type]
                params['svg_resolver'] = path_resolver_factory(sml)
            style = Style.from_file(filename, **params)

        _style_cache[key] = style

    return style


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


def _reraise_qgis_exception(exc, cls):
    if isinstance(exc, StyleTypeMismatch):
        raise cls(message=_("Layer type mismatch.")) from exc
    elif isinstance(exc, StyleValidationError):
        raise cls(message=_("QML file is not valid.")) from exc
    else:
        raise exc


_FIELD_TYPE_TO_QGIS = {
    FIELD_TYPE.INTEGER: (Layer.FT_INTEGER, _convert_none),
    FIELD_TYPE.BIGINT: (Layer.FT_INTEGER64, _convert_none),
    FIELD_TYPE.REAL: (Layer.FT_REAL, _convert_none),
    FIELD_TYPE.STRING: (Layer.FT_STRING, _convert_none),
    FIELD_TYPE.DATE: (Layer.FT_DATE, _convert_date),
    FIELD_TYPE.TIME: (Layer.FT_TIME, _convert_time),
    FIELD_TYPE.DATETIME: (Layer.FT_DATETIME, _convert_datetime),
}
