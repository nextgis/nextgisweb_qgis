from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime, time
from enum import Enum
from io import BytesIO
from os.path import normpath
from os.path import sep as path_sep
from pathlib import Path
from textwrap import dedent
from typing import Any, Self
from uuid import UUID

import sqlalchemy as sa
import sqlalchemy.event as sa_event
import sqlalchemy.orm as orm
import transaction
from cachetools import LRUCache
from msgspec import UNSET, Struct, UnsetType
from PIL import Image as PILImage
from qgis_headless.util import to_pil as qgis_image_to_pil
from shapely.geometry import box
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from zope.interface import implementer

from nextgisweb.env import gettext, inject
from nextgisweb.lib import saext
from nextgisweb.lib.geometry import Geometry
from nextgisweb.lib.json import dumps as json_dumps
from nextgisweb.lib.logging import logger
from nextgisweb.lib.saext import Msgspec

from nextgisweb.core import maintenance_hook
from nextgisweb.core.exception import (
    InsufficientPermissions,
    OperationalError,
    UserException,
    ValidationError,
)
from nextgisweb.feature_layer import (
    FIELD_TYPE,
    GEOM_TYPE,
    FeatureLayerMixin,
    IFeatureLayer,
    IFilterableFeatureLayer,
)
from nextgisweb.file_storage import FileObj, FileStorageComponent
from nextgisweb.file_upload import FileUploadRef
from nextgisweb.raster_layer import RasterLayer, RasterLayerComponent
from nextgisweb.render import (
    IExtentRenderRequest,
    ILegendableStyle,
    ILegendSymbols,
    IRenderableScaleRange,
    IRenderableStyle,
    ITileRenderRequest,
    LegendSymbol,
)
from nextgisweb.resmeta import ResourceMetadataItem
from nextgisweb.resource import (
    DataScope,
    Resource,
    ResourceScope,
    SAttribute,
    Serializer,
    SResource,
)
from nextgisweb.resource.model import ResourceRef
from nextgisweb.sld import SLD
from nextgisweb.sld.model import Style as SLDStyle
from nextgisweb.spatial_ref_sys import SRS
from nextgisweb.svg_marker_library import SVGMarkerLibrary, SVGMarkerLibraryComponent

import qgis_headless as qh
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

from .component import QgisComponent
from .util import (
    MD5_NULL_HEXDIGEST,
    file_md5_hexdigest,
    rand_color,
    sld_fix_vector,
    sld_to_qml_raster,
)

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
    GEOM_TYPE.NONE: Layer.GT_NULL,
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
_FORMAT_2_HEADLESS = {
    QgisStyleFormat.SLD: StyleFormat.SLD,
    **_FILE_FORMAT_2_HEADLESS,
}
_HEADLESS_2_FILE_FORMAT = {v: k for k, v in _FILE_FORMAT_2_HEADLESS.items()}


def _render_bounds(
    extent: tuple[float, float, float, float], size: tuple[int, int], padding: int
) -> tuple[tuple[float, float, float, float], tuple[int, int], tuple[int, int, int, int]]:
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


class ScaleRangeCache(Struct, array_like=True):
    min_scale_denom: float | None
    max_scale_denom: float | None


class QgisStyleMixin:
    @declared_attr
    def qgis_format(cls) -> Mapped[QgisStyleFormat]:
        return mapped_column(saext.Enum(QgisStyleFormat), default=QgisStyleFormat.DEFAULT)

    @declared_attr
    def qgis_fileobj_id(cls) -> Mapped[int | None]:
        return mapped_column(sa.ForeignKey(FileObj.id))

    @declared_attr
    def qgis_fileobj(cls) -> Mapped[FileObj | None]:
        return orm.relationship(cascade="save-update,merge")

    @declared_attr
    def qgis_sld_id(cls) -> Mapped[int | None]:
        return mapped_column(sa.ForeignKey(SLD.id))

    @declared_attr
    def qgis_sld(cls) -> Mapped[SLD | None]:
        return orm.relationship(cascade="save-update,merge")

    @declared_attr
    def qgis_scale_range_cache(cls) -> Mapped[ScaleRangeCache | None]:
        return mapped_column(Msgspec(ScaleRangeCache))

    @classmethod
    def _qgis_format_check(cls) -> sa.CheckConstraint:
        sql = """
            CASE qgis_format
                WHEN 'default' THEN qgis_sld_id IS NULL AND qgis_fileobj_id IS NULL
                WHEN 'sld' THEN qgis_sld_id IS NOT NULL AND qgis_fileobj_id IS NULL
                WHEN 'sld_file' THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
                WHEN 'qml_file' THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
                ELSE false
            END
        """
        return sa.CheckConstraint(dedent(sql).strip(), name="qgis_format_check")

    def from_file(
        self, filename: Path | str, *, format_: QgisStyleFormat = QgisStyleFormat.QML_FILE
    ) -> Self:
        self.qgis_format = format_
        self.qgis_fileobj = FileObj().copy_from(filename)
        return self

    @inject()
    def _update_scale_range_cache(self, *, qgis: QgisComponent = inject.arg()) -> None:
        qgis.qgis_init()
        assert isinstance(self, (QgisRasterStyle, QgisVectorStyle))
        sr = read_style(self).scale_range()
        self.qgis_scale_range_cache = ScaleRangeCache(*sr)

    def scale_range(self) -> tuple[float | None, float | None]:
        if self.qgis_scale_range_cache is None:
            self._update_scale_range_cache()
        assert (c := self.qgis_scale_range_cache) is not None
        return (c.min_scale_denom, c.max_scale_denom)


def update_not_modified(
    resource: QgisRasterStyle | QgisVectorStyle,
    source: Path | None,
    resmeta: str,
    *,
    format: QgisStyleFormat = QgisStyleFormat.QML_FILE,
    hash_default: str = MD5_NULL_HEXDIGEST,
) -> bool:
    for rmi in resource.resmeta:  # ty: ignore[missing-attribute]
        if rmi.key == resmeta:
            hash_expected = rmi.value
            break
    else:
        hash_expected = None

    if hash_expected is None:
        update = resource.qgis_format is None
        hash_existing = None
    else:
        if resource.qgis_format == QgisStyleFormat.DEFAULT:
            hash_existing = hash_default
        elif resource.qgis_format != format:
            return False
        else:
            assert resource.qgis_fileobj, f"Missing qgis_fileobj, {resource.qgis_format=}"
            hash_existing = file_md5_hexdigest(resource.qgis_fileobj.filename())
        update = hash_existing == hash_expected

    if not update:
        return False

    if source is None:
        resource.qgis_format = QgisStyleFormat.DEFAULT
        resource.qgis_fileobj = None
        hash_new = hash_default
    else:
        hash_new = file_md5_hexdigest(source)
        if hash_new == hash_existing:
            return True

        resource.qgis_format = format
        resource.qgis_fileobj = FileObj().copy_from(source)

    for rmi in resource.resmeta:  # ty: ignore[missing-attribute]
        if rmi.key == resmeta:
            rmi.value = hash_new
            break
    else:
        rmi = ResourceMetadataItem(key=resmeta)
        rmi.value = hash_new
        resource.resmeta.append(rmi)  # ty: ignore[missing-attribute]

    return True


@implementer(IRenderableStyle, ILegendSymbols, IRenderableScaleRange)
class QgisRasterStyle(QgisStyleMixin, Resource):
    identity = "qgis_raster_style"
    cls_display_name = gettext("QGIS raster style")
    cls_order = 60

    __table_args__ = (QgisStyleMixin._qgis_format_check(),)

    __scope__ = DataScope

    @classmethod
    def check_parent(cls, parent: Resource) -> bool:
        return isinstance(parent, RasterLayer)

    @property
    def raster_layer(self) -> RasterLayer:
        return self.ensure_parent(RasterLayer)

    @property
    def srs(self) -> SRS:
        return self.raster_layer.srs

    def render_request(self, srs: SRS, cond: dict | None = None) -> RenderRequest:
        return RenderRequest(self, srs)

    @inject()
    def _qgis_layer(self, *, raster_layer: RasterLayerComponent = inject.arg()) -> Layer:
        parent = self.raster_layer
        if parent.storage is not None:
            assert parent.storage_filename is not None
            parent.storage.configure_gdal()
            # Use vrt:// to prevent a cache removal.
            # QgsGdalProvider removes the network cache at each layer open.
            # The removal clears the shared CURL cache with the S3 data.
            # Keep the cache to reuse the S3 data at the next open.
            # See https://github.com/qgis/QGIS/pull/57388
            gdal_path = "vrt://" + parent.storage.vsi_path(parent.storage_filename)
        else:
            assert parent.fileobj is not None
            # We need raster pyramids so use working directory filename instead of
            # original filename.
            gdal_path = raster_layer.workdir_path(
                parent.fileobj,
                parent.fileobj_pam,
            )
        return Layer.from_gdal(str(gdal_path))

    @inject()
    def _render_image(
        self,
        srs: SRS,
        extent: tuple[float, float, float, float],
        size: tuple[int, int],
        *,
        qgis: QgisComponent = inject.arg(),
    ) -> PILImage.Image | None:
        qgis.qgis_init()

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

    @inject()
    def legend_symbols(
        self, icon_size: int, *, qgis: QgisComponent = inject.arg()
    ) -> list[LegendSymbol]:
        qgis.qgis_init()

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
                    parent=s.parent(),
                    render=None,
                    display_name=dn,
                    icon=qgis_image_to_pil(s.icon()),
                )
            )
        return result

    def _headless_kwargs(self) -> dict[str, Any]:
        return {
            "format": _FORMAT_2_HEADLESS[self.qgis_format],
            "layer_type": LT_RASTER,
        }


@inject()
def path_resolver_factory(
    sml: SVGMarkerLibrary | None,
    *,
    svg_marker_library: SVGMarkerLibraryComponent = inject.arg(),
) -> Callable[[str], str]:
    def path_resolver(name: str) -> str:
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
            filename = svg_marker_library.lookup(candidate, sml)
            if filename is not None:
                return filename

        return name

    return path_resolver


@implementer(IRenderableStyle, ILegendableStyle, ILegendSymbols, IRenderableScaleRange)
class QgisVectorStyle(QgisStyleMixin, Resource):
    identity = "qgis_vector_style"
    cls_display_name = gettext("QGIS vector style")
    cls_order = 60

    __scope__ = DataScope

    svg_marker_library_id: Mapped[int | None] = mapped_column(sa.ForeignKey(SVGMarkerLibrary.id))

    __table_args__ = (QgisStyleMixin._qgis_format_check(),)

    svg_marker_library: Mapped[SVGMarkerLibrary | None] = orm.relationship(
        foreign_keys=svg_marker_library_id,
        cascade="save-update,merge",
        # Backref is just for cleaning up QgisVectorStyle -> SVGMarkerLibrary
        # reference. SQLAlchemy does this automatically.
        backref=orm.backref("_backref_qgis_vector_style"),
    )

    @classmethod
    def check_parent(cls, parent: Resource) -> bool:
        return IFeatureLayer.providedBy(parent)

    @property
    def feature_layer(self) -> FeatureLayerMixin:
        return self.ensure_parent(FeatureLayerMixin)

    @property
    def srs(self) -> SRS | None:
        return self.feature_layer.srs

    def render_request(self, srs: SRS, cond: dict | None = None) -> RenderRequest:
        return RenderRequest(self, srs, cond)

    @inject()
    def _render_image(
        self,
        srs: SRS,
        extent: tuple[float, float, float, float],
        size: tuple[int, int],
        *,
        symbols: list[int] | None = None,
        feature_filter: Any = None,
        padding: int | None = None,
        qgis: QgisComponent = inject.arg(),
    ) -> PILImage.Image | None:
        feature_layer = self.feature_layer

        geometry_type = feature_layer.geometry_type
        if geometry_type == GEOM_TYPE.NONE:
            return

        qgis.qgis_init()

        style = read_style(self)
        if not check_scale_range(style, extent, size, dpi=96):
            return None

        if padding is not None:
            extended, render_size, target_box = _render_bounds(extent, size, padding)
        else:
            extended, render_size = extent, size

        feature_query = feature_layer.feature_query()
        if feature_filter is not None and IFilterableFeatureLayer.providedBy(feature_layer):
            filter_parser = feature_layer.filter_parser  # ty: ignore[missing-attribute]
            filter_program = filter_parser.parse(feature_filter)
            feature_query.set_filter_program(filter_program)
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

        qhl_fields = []
        cnv_fields = []
        qry_fields = []

        for field in feature_layer.fields:
            fkeyname = field.keyname
            if (style_attrs is not None) and (fkeyname.lower() not in style_attrs):
                continue
            field_to_qgis = _FIELD_TYPE_TO_QGIS[field.datatype]
            qhl_fields.append((fkeyname, field_to_qgis[0]))
            cnv_fields.append((fkeyname, field_to_qgis[1]))
            qry_fields.append(fkeyname)

        feature_query.fields(*qry_fields)

        features = []
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
            _GEOM_TYPE_TO_QGIS[geometry_type], crs, tuple(qhl_fields), tuple(features)
        )

        idx = mreq.add_layer(layer, style)

        render_params = {}
        if symbols is not None:
            render_params["symbols"] = ((idx, symbols),)
        res = mreq.render_image(extended, render_size, **render_params)
        im = qgis_image_to_pil(res)

        if padding is not None:
            im = im.crop(target_box)
            assert im.size == tuple(size)

        return im

    @inject()
    def render_legend(self, *, qgis: QgisComponent = inject.arg()) -> BytesIO:
        if self.feature_layer.geometry_type == GEOM_TYPE.NONE:
            img = PILImage.new("RGBA", (24, 24), (0, 0, 0, 0))
        else:
            qgis.qgis_init()

            mreq = MapRequest()
            mreq.set_dpi(96)

            style = read_style(self)
            layer = self._dummy_layer()

            mreq.add_layer(layer, style)
            res = mreq.render_legend()
            img = qgis_image_to_pil(res)

        # PNG-compressed buffer is required for render_legend()
        # TODO: Switch to PIL Image in future!
        buf = BytesIO()
        img.save(buf, "png")
        buf.seek(0)
        return buf

    @inject()
    def legend_symbols(
        self, icon_size: int, *, qgis: QgisComponent = inject.arg()
    ) -> list[LegendSymbol]:
        if self.feature_layer.geometry_type == GEOM_TYPE.NONE:
            return []

        qgis.qgis_init()

        mreq = MapRequest()
        mreq.set_dpi(96)

        style = read_style(self)
        layer = self._dummy_layer()
        mreq.add_layer(layer, style)

        return [
            LegendSymbol(
                index=s.index(),
                parent=s.parent(),
                render=s.render(),
                display_name=s.title(),  # ty: ignore[invalid-argument-type]
                icon=qgis_image_to_pil(s.icon()),
            )
            for s in mreq.legend_symbols(0, (icon_size, icon_size))
        ]

    def _dummy_layer(self) -> Layer:
        feature_layer = self.feature_layer
        return Layer.from_data(
            _GEOM_TYPE_TO_QGIS[feature_layer.geometry_type],
            CRS.from_epsg(feature_layer.srs.id),
            (),
            (),
        )

    def _headless_kwargs(self) -> dict[str, Any]:
        return {
            "format": _FORMAT_2_HEADLESS[self.qgis_format],
            "layer_type": LT_VECTOR,
            "layer_geometry_type": _GEOM_TYPE_TO_QGIS[self.feature_layer.geometry_type],
        }


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
    def __init__(
        self, style: QgisRasterStyle | QgisVectorStyle, srs: SRS, cond: dict | None = None
    ) -> None:
        self.style = style
        self.srs = srs
        self.params = dict[str, Any]()
        if isinstance(style, QgisVectorStyle):
            if cond is not None:
                if "symbols" in cond:
                    self.params["symbols"] = tuple(cond["symbols"])
                if "filter" in cond:
                    self.params["feature_filter"] = cond["filter"]

    def render_extent(
        self, extent: tuple[float, float, float, float], size: tuple[int, int]
    ) -> PILImage.Image | None:
        try:
            return self.style._render_image(self.srs, extent, size, **self.params)
        except Exception as exc:
            _reraise_qgis_exception(exc, OperationalError)

    def render_tile(self, tile: tuple[int, int, int], size: int) -> PILImage.Image | None:
        extent = self.srs.tile_extent(tile)
        params = dict(self.params)
        if isinstance(self.style, QgisVectorStyle):
            params["padding"] = 64
        try:
            return self.style._render_image(self.srs, extent, (size, size), **params)
        except Exception as exc:
            _reraise_qgis_exception(exc, OperationalError)


class FormatAttr(SAttribute):
    def get(self, srlzr: Serializer) -> QgisStyleFormat:
        return srlzr.obj.qgis_format

    def set(self, srlzr: Serializer, value: QgisStyleFormat, *, create: bool) -> None:
        if (srlzr.data.file_upload is UNSET) and value in (
            QgisStyleFormat.QML_FILE,
            QgisStyleFormat.SLD_FILE,
        ):
            raise ValidationError(gettext("Style format mismatch."))

        if value == QgisStyleFormat.DEFAULT:
            srlzr.obj.qgis_fileobj = None
            srlzr.obj.qgis_sld = None
        srlzr.obj.qgis_format = value


class SldAttr(SAttribute):
    def get(self, srlzr: Serializer) -> SLDStyle | UnsetType:
        if srlzr.obj.qgis_format == QgisStyleFormat.SLD:
            return srlzr.obj.qgis_sld.value
        else:
            return UNSET

    def set(self, srlzr: Serializer, value: SLDStyle, *, create: bool) -> None:
        if srlzr.obj.qgis_format != QgisStyleFormat.SLD:
            raise ValidationError(gettext("Style format mismatch."))

        sld = SLD()
        sld.deserialize(value)

        sld_xml = sld.to_xml()

        params = srlzr.obj._headless_kwargs()
        if isinstance(srlzr.obj, QgisRasterStyle):
            xml = sld_to_qml_raster(sld_xml)
            params["format"] = StyleFormat.QML
        else:
            xml = sld_fix_vector(sld_xml)
            params["format"] = StyleFormat.SLD

        QgisComponent.current().qgis_init()

        try:
            Style.from_string(xml, **params)
        except Exception as exc:
            _reraise_qgis_exception(exc, ValidationError)

        srlzr.obj.qgis_sld = sld
        srlzr.obj.qgis_fileobj = None


class FileUploadAttr(SAttribute):
    def get(self, srlzr: Serializer) -> UnsetType:
        return UNSET

    def set(self, srlzr: Serializer, value: FileUploadRef, *, create: bool) -> None:
        if srlzr.data.format is UNSET:
            # Force style format autodetection
            srlzr.obj.qgis_format = None

        QgisComponent.current().qgis_init()

        srcfile = str(value().data_path)

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

        srlzr.obj.qgis_fileobj = value().to_fileobj()
        srlzr.obj.qgis_sld = None


class CopyFromAttr(SAttribute):
    def get(self, srlzr: Serializer) -> UnsetType:
        return UNSET

    def set(self, srlzr: Serializer, value: ResourceRef, *, create: bool) -> None:
        style = srlzr.resclass.filter_by(id=value.id).one()
        if not style.has_permission(ResourceScope.read, srlzr.user):
            raise InsufficientPermissions()  # TODO: Add more details

        for attr in ("qgis_format", "qgis_fileobj", "qgis_sld", "svg_marker_library"):
            if hasattr(style, attr):
                setattr(srlzr.obj, attr, getattr(style, attr))

        if (fobj := srlzr.obj.qgis_fileobj) is not None:
            QgisComponent.current().qgis_init()
            try:
                Style.from_file(
                    str(fobj.filename()),
                    **srlzr.obj._headless_kwargs(),
                )
            except Exception as exc:
                _reraise_qgis_exception(exc, ValidationError)


class QgisVectorStyleSerializer(Serializer, resource=QgisVectorStyle):
    format = FormatAttr(read=ResourceScope.read, write=ResourceScope.update)
    sld = SldAttr(read=ResourceScope.read, write=ResourceScope.update)
    file_upload = FileUploadAttr(read=None, write=ResourceScope.update)
    copy_from = CopyFromAttr(read=None, write=ResourceScope.update)
    svg_marker_library = SResource(read=ResourceScope.read, write=ResourceScope.update)


class QgisRasterStyleSerializer(Serializer, resource=QgisRasterStyle):
    format = FormatAttr(read=ResourceScope.read, write=ResourceScope.update)
    sld = SldAttr(read=ResourceScope.read, write=ResourceScope.update)
    file_upload = FileUploadAttr(read=None, write=ResourceScope.update)
    copy_from = CopyFromAttr(read=None, write=ResourceScope.update)


_style_cache = LRUCache(maxsize=256)


def _cache_key(
    qgis_style: QgisRasterStyle | QgisVectorStyle,
) -> int | str | tuple[str, datetime | None, str]:
    if qgis_style.qgis_format == QgisStyleFormat.DEFAULT:
        return qgis_style.id

    if qgis_style.qgis_format == QgisStyleFormat.SLD:
        uuid = UUID(int=qgis_style.qgis_sld_id, version=4).hex
    else:
        assert qgis_style.qgis_fileobj_id is not None
        uuid = UUID(int=2**127 + qgis_style.qgis_fileobj_id, version=4).hex

    if isinstance(qgis_style, QgisRasterStyle):
        return uuid

    sml = qgis_style.svg_marker_library
    return (
        uuid,
        None if sml is None else sml.tstamp,
        qgis_style.ensure_parent(FeatureLayerMixin).geometry_type,
    )


@inject()
def _read_style(
    qgis_style: QgisRasterStyle | QgisVectorStyle,
    *,
    file_storage: FileStorageComponent = inject.arg(),
) -> Style:
    is_vector = isinstance(qgis_style, QgisVectorStyle)

    params = dict[str, Any]()
    params["layer_type"] = LT_VECTOR if is_vector else LT_RASTER
    if is_vector:
        params["layer_geometry_type"] = _GEOM_TYPE_TO_QGIS[qgis_style.feature_layer.geometry_type]

    # Default
    if qgis_style.qgis_format == QgisStyleFormat.DEFAULT:
        if is_vector:
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
            params["random_seed"] = qgis_style.ensure_id()
        return Style.from_defaults(**params)

    if is_vector:
        params["svg_resolver"] = path_resolver_factory(qgis_style.svg_marker_library)

    # User-defined SLD
    if qgis_style.qgis_format == QgisStyleFormat.SLD:
        assert qgis_style.qgis_sld is not None
        sld_xml = qgis_style.qgis_sld.to_xml()
        if isinstance(qgis_style, QgisRasterStyle):
            # We have to convert to QML until QGIS supports raster SLD import
            xml = sld_to_qml_raster(sld_xml)
            params["format"] = StyleFormat.QML
        else:
            xml = sld_fix_vector(sld_xml)
            params["format"] = StyleFormat.SLD
        return Style.from_string(xml, **params)

    # QML or SLD file
    params["format"] = _FILE_FORMAT_2_HEADLESS[qgis_style.qgis_format]
    # NOTE: Some file objects can have component != 'qgis'
    filename = file_storage.filename(qgis_style.qgis_fileobj)
    return Style.from_file(filename, **params)


def read_style(qgis_style: QgisRasterStyle | QgisVectorStyle) -> Style:
    key = _cache_key(qgis_style)
    if (style := _style_cache.get(key)) is None:
        style = _style_cache[key] = _read_style(qgis_style)
    return style


def _update_scale_range_cache_event(
    mapper: orm.Mapper, connection: sa.Connection, qgis_style: QgisRasterStyle | QgisVectorStyle
) -> None:
    attrs_state = sa.inspect(qgis_style, raiseerr=True).attrs
    for attr in ("qgis_format", "qgis_fileobj_id", "qgis_sld_id"):
        history = getattr(attrs_state, attr).load_history()
        if history.has_changes():
            qgis_style._update_scale_range_cache()
            return


for cls in (QgisRasterStyle, QgisVectorStyle):
    for event in ("before_insert", "before_update"):
        sa_event.listens_for(cls, event)(_update_scale_range_cache_event)


def check_scale_range(
    style: Style,
    extent: tuple[float, float, float, float],
    size: tuple[int, int],
    *,
    dpi: int,
) -> bool:
    min_denom, max_denom = style.scale_range()
    if min_denom is None and max_denom is None:
        return True

    denom = (extent[2] - extent[0]) * dpi / (size[0] * 0.0254)
    return (min_denom is None or min_denom > denom) and (max_denom is None or max_denom < denom)


@maintenance_hook()
def maintenance(comp: QgisComponent) -> None:
    with transaction.manager:
        for cls in (QgisRasterStyle, QgisVectorStyle):
            for resource in cls.filter_by(qgis_scale_range_cache=None):
                try:
                    resource._update_scale_range_cache()
                except qh.StyleValidationError as e:
                    logger.warning(f"QGIS style (id={resource.id}) error: {e}")


def _convert_none(v: None) -> None:
    return v


def _convert_json(v: dict | None) -> str | None:
    if v is not None:
        return json_dumps(v)


def _convert_date(v: date | None) -> tuple[int, int, int] | None:
    if v is not None:
        return v.timetuple()[0:3]


def _convert_time(v: time | None) -> tuple[int, int, int] | None:
    if v is not None:
        return (v.hour, v.minute, v.second)


def _convert_datetime(v: datetime | None) -> tuple[int, int, int, int, int, int] | None:
    if v is not None:
        return v.timetuple()[0:6]


def _reraise_qgis_exception(exc: Exception, cls: type[UserException]) -> None:
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
    FIELD_TYPE.BOOLEAN: (Layer.FT_BOOLEAN, _convert_none),
    FIELD_TYPE.JSON: (Layer.FT_JSON, _convert_json),
}
