import re
from enum import Enum
from io import BytesIO
from os.path import normpath
from os.path import sep as path_sep
from uuid import UUID

from cachetools import LRUCache
from shapely.geometry import box
from sqlalchemy.orm import declared_attr
from zope.interface import implementer

from nextgisweb.env import Base, DBSession, env, gettext
from nextgisweb.lib import db
from nextgisweb.lib.geometry import Geometry

from nextgisweb.core.exception import InsufficientPermissions, OperationalError, ValidationError
from nextgisweb.feature_layer import FIELD_TYPE, GEOM_TYPE, IFeatureLayer
from nextgisweb.file_storage import FileObj
from nextgisweb.file_upload import FileUpload
from nextgisweb.render import (
    IExtentRenderRequest,
    ILegendableStyle,
    ILegendSymbols,
    IRenderableScaleRange,
    IRenderableStyle,
    ITileRenderRequest,
    LegendSymbol,
)
from nextgisweb.resource import DataScope, Resource, ResourceScope, Serializer
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
        return db.relationship(FileObj, cascade="save-update, merge")

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
        self.qgis_fileobj = FileObj().copy_from(filename)
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


@implementer(IRenderableStyle, ILegendSymbols, IRenderableScaleRange)
class QgisRasterStyle(Base, QgisStyleMixin, Resource):
    identity = "qgis_raster_style"
    cls_display_name = gettext("QGIS raster style")
    cls_order = 60

    __scope__ = DataScope

    @classmethod
    def check_parent(cls, parent):
        return parent.cls == "raster_layer"

    def render_request(self, srs, cond=None):
        return RenderRequest(self, srs)

    def _qgis_layer(self):
        # We need raster pyramids so use working directory filename
        # instead of original filename.
        gdal_path = env.raster_layer.workdir_path(self.parent.fileobj)
        return Layer.from_gdal(str(gdal_path))

    def _render_image(self, srs, extent, size):
        env.qgis.qgis_init()

        style = read_style(self)
        if not check_scale_range(style, extent, size, dpi=96):
            return None

        mreq = MapRequest()
        mreq.set_dpi(96)
        mreq.set_crs(CRS.from_epsg(srs.id))

        layer = self._qgis_layer()
        mreq.add_layer(layer, style)

        res = mreq.render_image(extent, size)
        img = qgis_image_to_pil(res)

        return img

    def legend_symbols(self, icon_size):
        env.qgis.qgis_init()

        mreq = MapRequest()
        mreq.set_dpi(96)

        style = read_style(self)
        layer = self._qgis_layer()
        mreq.add_layer(layer, style)

        result = []
        for s in mreq.legend_symbols(0, (icon_size, icon_size)):
            if title := s.title():
                dn = title
            else:
                dn = gettext("Band {}").format(s.raster_band())
            result.append(
                LegendSymbol(
                    index=s.index(),
                    render=None,
                    display_name=dn,
                    icon=qgis_image_to_pil(s.icon()),
                )
            )
        return result

    def scale_range(self):
        env.qgis.qgis_init()
        return read_style(self).scale_range()

    def _headless_kwargs(self):
        return dict(
            format=_FILE_FORMAT_2_HEADLESS[self.qgis_format],
            layer_type=LT_RASTER,
        )


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
    cls_display_name = gettext("QGIS vector style")
    cls_order = 60

    __scope__ = DataScope

    svg_marker_library_id = db.Column(db.ForeignKey(SVGMarkerLibrary.id), nullable=True)
    svg_marker_library = db.relationship(
        SVGMarkerLibrary,
        foreign_keys=svg_marker_library_id,
        cascade="save-update, merge",
        # Backref is just for cleaning up QgisVectorStyle -> SVGMarkerLibrary
        # reference. SQLAlchemy does this automatically.
        backref=db.backref("_backref_qgis_vector_style", cascade_backrefs=False),
    )

    @classmethod
    def check_parent(cls, parent):
        return IFeatureLayer.providedBy(parent)

    @property
    def feature_layer(self):
        return self.parent

    def render_request(self, srs, cond=None):
        return RenderRequest(self, srs, cond)

    def _render_image(self, srs, extent, size, *, symbols=None, padding=0):
        extended, render_size, target_box = _render_bounds(extent, size, padding)

        env.qgis.qgis_init()

        style = read_style(self)
        if not check_scale_range(style, extent, size, dpi=96):
            return None

        feature_query = self.parent.feature_query()
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

        idx = mreq.add_layer(layer, style)

        render_params = dict()
        if symbols is not None:
            render_params["symbols"] = ((idx, symbols),)
        res = mreq.render_image(extent, size, **render_params)
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
            LegendSymbol(
                index=s.index(),
                render=s.render(),
                display_name=s.title(),
                icon=qgis_image_to_pil(s.icon()),
            )
            for s in mreq.legend_symbols(0, (icon_size, icon_size))
        ]

    def scale_range(self):
        env.qgis.qgis_init()
        return read_style(self).scale_range()

    def _headless_kwargs(self):
        return dict(
            format=_FILE_FORMAT_2_HEADLESS[self.qgis_format],
            layer_type=LT_VECTOR,
            layer_geometry_type=_GEOM_TYPE_TO_QGIS[self.parent.geometry_type],
        )


DataScope.read.require(DataScope.read, attr="parent", cls=QgisRasterStyle)
DataScope.read.require(DataScope.read, attr="parent", cls=QgisVectorStyle)
DataScope.read.require(
    ResourceScope.read,
    attr="svg_marker_library",
    attr_empty=True,
    cls=QgisVectorStyle,
)


@implementer(IExtentRenderRequest, ITileRenderRequest)
class RenderRequest:
    def __init__(self, style, srs, cond=None):
        self.style = style
        self.srs = srs
        self.params = dict()
        if isinstance(style, QgisVectorStyle):
            if cond is not None and "symbols" in cond:
                self.params["symbols"] = tuple(cond["symbols"])

    def render_extent(self, extent, size):
        try:
            return self.style._render_image(self.srs, extent, size, **self.params)
        except Exception as exc:
            _reraise_qgis_exception(exc, OperationalError)

    def render_tile(self, tile, size):
        extent = self.srs.tile_extent(tile)
        params = dict(self.params)
        if isinstance(self.style, QgisVectorStyle):
            params["padding"] = size / 2
        try:
            return self.style._render_image(self.srs, extent, (size, size), **params)
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
            raise ValidationError(message=gettext("Style format mismatch."))
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
            raise ValidationError(message=gettext("Style format mismatch."))
        sld = SLD()
        sld.deserialize(value)
        srlzr.obj.qgis_sld = sld
        srlzr.obj.qgis_fileobj = None


class _file_upload_attr(SP):
    def setter(self, srlzr, value):
        # Force style format autodetection
        if "format" not in srlzr.data:
            srlzr.obj.qgis_format = None

        env.qgis.qgis_init()

        fupload = FileUpload(id=value["id"])
        srcfile = str(fupload.data_path)

        if srlzr.obj.qgis_format in _FILE_FORMAT_2_HEADLESS:
            pass  # Already set in format attribute
        elif srlzr.obj.qgis_format is None:
            for fmt in (StyleFormat.QML, StyleFormat.SLD):
                try:
                    Style.from_file(srcfile, format=fmt)
                except StyleValidationError:
                    pass
                else:
                    srlzr.obj.qgis_format = _HEADLESS_2_FILE_FORMAT[fmt]
                    break
            else:
                raise ValidationError(message=gettext("Style file is not valid."))
        else:
            raise ValidationError(message=gettext("Style format mismatch."))

        try:
            Style.from_file(srcfile, **srlzr.obj._headless_kwargs())
        except Exception as exc:
            _reraise_qgis_exception(exc, ValidationError)

        srlzr.obj.qgis_fileobj = fupload.to_fileobj()
        srlzr.obj.qgis_sld = None


class _copy_from(SP):
    def setter(self, srlzr, value):
        with DBSession.no_autoflush:
            style = srlzr.resclass.filter_by(id=value["id"]).one()
            if not style.has_permission(ResourceScope.read, srlzr.user):
                raise InsufficientPermissions()  # TODO: Add more details
            for attr in ("qgis_format", "qgis_fileobj", "qgis_sld", "svg_marker_library"):
                if hasattr(style, attr):
                    setattr(srlzr.obj, attr, getattr(style, attr))

            if (fobj := srlzr.obj.qgis_fileobj) is not None:
                env.qgis.qgis_init()
                try:
                    Style.from_file(
                        str(fobj.filename()),
                        **srlzr.obj._headless_kwargs(),
                    )
                except Exception as exc:
                    _reraise_qgis_exception(exc, ValidationError)


class QgisVectorStyleSerializer(Serializer):
    identity = QgisVectorStyle.identity
    resclass = QgisVectorStyle

    format = _format_attr(read=ResourceScope.read, write=ResourceScope.update)
    sld = _sld_attr(read=ResourceScope.read, write=ResourceScope.update)
    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)
    svg_marker_library = SRR(read=ResourceScope.read, write=ResourceScope.update)
    copy_from = _copy_from(read=None, write=ResourceScope.update)


class QgisRasterStyleSerializer(Serializer):
    identity = QgisRasterStyle.identity
    resclass = QgisRasterStyle

    format = _format_attr(read=ResourceScope.read, write=ResourceScope.update)
    sld = _sld_attr(read=ResourceScope.read, write=ResourceScope.update)
    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)
    copy_from = _copy_from(read=None, write=ResourceScope.update)


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
        raise cls(message=gettext("Layer type mismatch.")) from exc
    elif isinstance(exc, StyleValidationError):
        raise cls(message=gettext("Style file is not valid.")) from exc
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
