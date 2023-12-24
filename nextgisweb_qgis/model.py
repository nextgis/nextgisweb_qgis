import re
from enum import Enum
from io import BytesIO
from os.path import normpath
from os.path import sep as path_sep
from shutil import copyfile
from uuid import UUID
from warnings import warn

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
    IRenderableScaleRange,
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
from nextgisweb.sld import SLD
from nextgisweb.svg_marker_library import SVGMarkerLibrary

from qgis_headless import (
    CRS,
    LT_RASTER,
    LT_VECTOR,
    Layer,
    MapRequest,
    Style,
    StyleFormat,
    StyleTypeMismatch,
    StyleValidationError,
)
from qgis_headless.util import to_pil as qgis_image_to_pil

from .util import rand_color, sld_to_qml_raster

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
    r"^(/usr/share/qgis/svg/|/Users/[^/]+/|/home/[^/]+/|(../)+|/)", re.IGNORECASE
)


class QgisStyleFormat(Enum):
    DEFAULT = "default"
    QML_FILE = "qml_file"
    SLD_FILE = "sld_file"
    SLD = "sld"


_FILE_FORMAT_2_HEADLESS = {
    QgisStyleFormat.QML_FILE: StyleFormat.QML,
    QgisStyleFormat.SLD_FILE: StyleFormat.SLD,
}
_HEADLESS_2_FILE_FORMAT = {v: k for k, v in _FILE_FORMAT_2_HEADLESS.items()}


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
    render_size = (size[0] + 2 * padding, size[1] + 2 * padding)

    # Crop box
    target_box = (padding, padding, size[0] + padding, size[1] + padding)

    return extended, render_size, target_box


class QgisStyleMixin:
    @declared_attr
    def qgis_format(cls):
        return db.Column(db.Enum(QgisStyleFormat), nullable=False, default=QgisStyleFormat.DEFAULT)

    @declared_attr
    def qgis_fileobj_id(cls):
        return db.Column(db.ForeignKey(FileObj.id), nullable=True)

    @declared_attr
    def qgis_fileobj(cls):
        return db.relationship(FileObj, cascade="all")

    @declared_attr
    def qgis_sld_id(cls):
        return db.Column(db.ForeignKey(SLD.id), nullable=True)

    @declared_attr
    def qgis_sld(cls):
        return db.relationship(SLD, cascade="save-update, merge")

    @property
    def srs(self):
        return self.parent.srs

    def from_file(self, filename, *, format_=QgisStyleFormat.QML_FILE):
        self.qgis_format = format_
        self.qgis_fileobj = env.file_storage.fileobj(COMP_ID)
        dstfile = env.file_storage.filename(self.qgis_fileobj, makedirs=True)
        copyfile(filename, dstfile)
        return self

    __table_args__ = (
        db.CheckConstraint(
            """
            CASE qgis_format
                WHEN 'default' THEN qgis_sld_id IS NULL AND qgis_fileobj_id IS NULL
                WHEN 'sld' THEN qgis_sld_id IS NOT NULL AND qgis_fileobj_id IS NULL
                WHEN 'sld_file' THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
                WHEN 'qml_file' THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
                ELSE false
            END
        """,
            name="qgis_format_check",
        ),
    )

    @property
    def qml_fileobj_id(self):
        warn(
            "Since nextgisweb_gis 2.9.0.dev1 use qgis_style.qgis_fileobj_id "
            "instead of qgis_style.qml_fileobj_id",
            DeprecationWarning,
            2,
        )
        return self.qgis_fileobj_id

    @qml_fileobj_id.setter
    def qml_fileobj_id(self, value):
        warn(
            "Since nextgisweb_gis 2.9.0.dev1 use qgis_style.qgis_fileobj_id "
            "instead of qgis_style.qml_fileobj_id",
            DeprecationWarning,
            2,
        )
        self.qgis_fileobj_id = value

    @property
    def qml_fileobj(self):
        warn(
            "Since nextgisweb_gis 2.9.0.dev1 use qgis_style.qgis_fileobj "
            "instead of qgis_style.qml_fileobj",
            DeprecationWarning,
            2,
        )
        return self.qgis_fileobj

    @qml_fileobj.setter
    def qml_fileobj(self, value):
        warn(
            "Since nextgisweb_gis 2.9.0.dev1 use qgis_style.qgis_fileobj "
            "instead of qgis_style.qml_fileobj",
            DeprecationWarning,
            2,
        )
        self.qgis_fileobj = value


@implementer(IRenderableStyle, IRenderableScaleRange)
class QgisRasterStyle(Base, QgisStyleMixin, Resource):
    identity = "qgis_raster_style"
    cls_display_name = _("QGIS raster style")

    __scope__ = DataScope

    @classmethod
    def check_parent(cls, parent):
        return parent.cls == "raster_layer"

    def render_request(self, srs):
        return RenderRequest(self, srs)

    def _render_image(self, srs, extent, size, cond=None, padding=0):
        extended, render_size, target_box = _render_bounds(extent, size, padding)

        env.qgis.qgis_init()

        style = read_style(self)
        if not check_scale_range(style, extent, size, dpi=96):
            return None

        # We need raster pyramids so use working directory filename
        # instead of original filename.
        gdal_path = env.raster_layer.workdir_filename(self.parent.fileobj)

        mreq = MapRequest()
        mreq.set_dpi(96)
        mreq.set_crs(CRS.from_epsg(srs.id))

        layer = Layer.from_gdal(gdal_path)
        mreq.add_layer(layer, style)

        res = mreq.render_image(extent, size)
        img = qgis_image_to_pil(res)

        return img

    def scale_range(self):
        env.qgis.qgis_init()
        return read_style(self).scale_range()


def path_resolver_factory(svg_marker_library):
    def path_resolver(name):
        if name.startswith(("http://", "https://", "base64:")):
            return name

        name_library = normpath(name)
        name_library = STRIP_SVG_PATH.sub("", name_library)
        name_library = re.sub(r"\.svg$", "", name_library)

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


@implementer(IRenderableStyle, ILegendableStyle, ILegendSymbols, IRenderableScaleRange)
class QgisVectorStyle(Base, QgisStyleMixin, Resource):
    identity = "qgis_vector_style"
    cls_display_name = _("QGIS vector style")

    __scope__ = (DataScope, DataStructureScope)

    svg_marker_library_id = db.Column(db.ForeignKey(SVGMarkerLibrary.id), nullable=True)
    svg_marker_library = db.relationship(
        SVGMarkerLibrary,
        foreign_keys=svg_marker_library_id,
        cascade="save-update, merge",
        # Backref is just for cleaning up QgisVectorStyle -> SVGMarkerLibrary
        # reference. SQLAlchemy does this automatically.
        backref=db.backref("_backref_qgis_vector_style"),
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
        extended, render_size, target_box = _render_bounds(extent, size, padding)

        env.qgis.qgis_init()

        style = read_style(self)
        if not check_scale_range(style, extent, size, dpi=96):
            return None

        feature_query = self.parent.feature_query()

        # Apply filter condition
        if cond is not None:
            feature_query.filter_by(**cond)

        feature_query.srs(srs)

        bbox = Geometry.from_shape(box(*extended), srid=srs.id)
        feature_query.intersects(bbox)
        feature_query.geom()

        crs = CRS.from_epsg(srs.id)

        mreq = MapRequest()
        mreq.set_dpi(96)
        mreq.set_crs(crs)

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
            features.append(
                (
                    feat.id,
                    feat.geom.wkb,
                    tuple([convert(feat.fields[field]) for field, convert in cnv_fields]),
                )
            )

        if len(features) == 0:
            return None

        layer = Layer.from_data(
            _GEOM_TYPE_TO_QGIS[self.parent.geometry_type], crs, tuple(qhl_fields), tuple(features)
        )

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
            CRS.from_epsg(self.parent.srs.id),
            (),
            (),
        )

        mreq.add_layer(layer, style)
        res = mreq.render_legend()
        img = qgis_image_to_pil(res)

        # PNG-compressed buffer is required for render_legend()
        # TODO: Switch to PIL Image in future!
        buf = BytesIO()
        img.save(buf, "png")
        buf.seek(0)
        return buf

    def legend_symbols(self, icon_size):
        env.qgis.qgis_init()

        mreq = MapRequest()
        mreq.set_dpi(96)

        style = read_style(self)

        layer = Layer.from_data(
            _GEOM_TYPE_TO_QGIS[self.parent.geometry_type],
            CRS.from_epsg(self.parent.srs.id),
            (),
            (),
        )

        mreq.add_layer(layer, style)

        return [
            LegendSymbol(display_name=s.title(), icon=qgis_image_to_pil(s.icon()))
            for s in mreq.legend_symbols(0, (icon_size, icon_size))
        ]

    def scale_range(self):
        env.qgis.qgis_init()
        return read_style(self).scale_range()


DataScope.read.require(
    ResourceScope.read, cls=QgisVectorStyle, attr="svg_marker_library", attr_empty=True
)


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
                self.srs, extent, (size, size), self.cond, padding=size / 2
            )
        except Exception as exc:
            _reraise_qgis_exception(exc, OperationalError)


class _format_attr(SP):
    def getter(self, srlzr):
        return srlzr.obj.qgis_format

    def setter(self, srlzr, value):
        if value is None:
            value = QgisStyleFormat.DEFAULT
        else:
            value = QgisStyleFormat(value)
        if "file_upload" not in srlzr.data and value in (
            QgisStyleFormat.QML_FILE,
            QgisStyleFormat.SLD_FILE,
        ):
            raise ValidationError(message=_("Style format mismatch."))
        if value == QgisStyleFormat.DEFAULT:
            srlzr.obj.qgis_fileobj = None
            srlzr.obj.qgis_sld = None
        srlzr.obj.qgis_format = value


class _sld_attr(SP):
    def getter(self, srlzr):
        if srlzr.obj.qgis_format == QgisStyleFormat.SLD:
            return srlzr.obj.qgis_sld.value

    def setter(self, srlzr, value):
        if srlzr.obj.qgis_format != QgisStyleFormat.SLD:
            raise ValidationError(message=_("Style format mismatch."))
        srlzr.obj.qgis_sld = SLD(value=value)
        srlzr.obj.qgis_fileobj = None


class _file_upload_attr(SP):
    def setter(self, srlzr, value):
        # Force style format autodetection
        if "format" not in srlzr.data:
            srlzr.obj.qgis_format = None

        env.qgis.qgis_init()

        srcfile, meta = env.file_upload.get_filename(value["id"])

        params = dict()

        if srlzr.obj.qgis_format in _FILE_FORMAT_2_HEADLESS:
            params["format"] = _FILE_FORMAT_2_HEADLESS[srlzr.obj.qgis_format]
        elif srlzr.obj.qgis_format is None:
            for fmt in (StyleFormat.QML, StyleFormat.SLD):
                try:
                    Style.from_file(srcfile, format=fmt)
                except StyleValidationError:
                    pass
                else:
                    params["format"] = fmt
                    srlzr.obj.qgis_format = _HEADLESS_2_FILE_FORMAT[fmt]
                    break
            else:
                raise ValidationError(message=_("Style file is not valid."))
        else:
            raise ValidationError(message=_("Style format mismatch."))

        layer = srlzr.obj.parent
        if IFeatureLayer.providedBy(layer):
            params["layer_type"] = LT_VECTOR
            gt = layer.geometry_type
            gt_qgis = _GEOM_TYPE_TO_QGIS[gt]
            params["layer_geometry_type"] = gt_qgis
        else:
            params["layer_type"] = LT_RASTER

        try:
            Style.from_file(srcfile, **params)
        except Exception as exc:
            _reraise_qgis_exception(exc, ValidationError)

        fileobj = env.file_storage.fileobj(component=COMP_ID)
        dstfile = env.file_storage.filename(fileobj, makedirs=True)
        copyfile(srcfile, dstfile)

        srlzr.obj.qgis_fileobj = fileobj
        srlzr.obj.qgis_sld = None

        on_style_change.fire(srlzr.obj)


class QgisVectorStyleSerializer(Serializer):
    identity = QgisVectorStyle.identity
    resclass = QgisVectorStyle

    format = _format_attr(read=ResourceScope.read, write=ResourceScope.update)
    sld = _sld_attr(read=ResourceScope.read, write=ResourceScope.update)
    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)
    svg_marker_library = SRR(read=DataStructureScope.read, write=DataStructureScope.write)


class QgisRasterSerializer(Serializer):
    identity = QgisRasterStyle.identity
    resclass = QgisRasterStyle

    format = _format_attr(read=ResourceScope.read, write=ResourceScope.update)
    sld = _sld_attr(read=ResourceScope.read, write=ResourceScope.update)
    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)


_style_cache = LRUCache(maxsize=256)


def read_style(qgis_style):
    if qgis_style.qgis_format == QgisStyleFormat.DEFAULT:
        key = qgis_style.id

    else:
        if qgis_style.qgis_format == QgisStyleFormat.SLD:
            uuid = UUID(int=qgis_style.qgis_sld_id, version=4).hex
        else:
            uuid = qgis_style.qgis_fileobj.uuid

        if isinstance(qgis_style, QgisVectorStyle):
            sml = qgis_style.svg_marker_library
            geometry_type = qgis_style.parent.geometry_type
        else:
            sml = geometry_type = None

        key = (uuid, None if sml is None else sml.tstamp, geometry_type)

    if (style := _style_cache.get(key)) is None:
        params = dict()

        if qgis_style.qgis_format == QgisStyleFormat.DEFAULT:
            if isinstance(qgis_style, QgisVectorStyle):
                params["layer_type"] = LT_VECTOR
                params["layer_geometry_type"] = _GEOM_TYPE_TO_QGIS[qgis_style.parent.geometry_type]
                if params["layer_geometry_type"] in (
                    Layer.GT_POLYGON,
                    Layer.GT_POLYGONZ,
                    Layer.GT_MULTIPOLYGON,
                    Layer.GT_MULTIPOLYGONZ,
                ):
                    opacity = 63
                else:
                    opacity = 255
                params["color"] = rand_color(qgis_style.id) + (opacity,)
            else:
                params["layer_type"] = LT_RASTER
            style = Style.from_defaults(**params)

        else:
            if geometry_type is not None:
                params["layer_geometry_type"] = _GEOM_TYPE_TO_QGIS[geometry_type]
                params["svg_resolver"] = path_resolver_factory(sml)

            if qgis_style.qgis_format == QgisStyleFormat.SLD:
                xml = qgis_style.qgis_sld.to_xml()
                if isinstance(qgis_style, QgisRasterStyle):
                    # We have to convert to QML until QGIS supports raster SLD import
                    xml = sld_to_qml_raster(xml)
                    params["format"] = StyleFormat.QML
                else:
                    params["format"] = StyleFormat.SLD
                style = Style.from_string(xml, **params)
            else:
                params["format"] = _FILE_FORMAT_2_HEADLESS[qgis_style.qgis_format]
                # NOTE: Some file objects can have component != 'qgis'
                filename = env.file_storage.filename(qgis_style.qgis_fileobj)
                style = Style.from_file(filename, **params)

        _style_cache[key] = style

    return style


def check_scale_range(style, extent, size, *, dpi):
    min_denom, max_denom = style.scale_range()
    if min_denom is None and max_denom is None:
        return True

    denom = (extent[2] - extent[0]) * dpi / (size[0] * 0.0254)
    return (min_denom is None or min_denom > denom) and (max_denom is None or max_denom < denom)


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
        raise cls(message=_("Style file is not valid.")) from exc
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
