import pytest
from qgis_headless.util import image_stat, render_vector

from nextgisweb.lib.geometry import Geometry

from nextgisweb.sld import model as sldm
from nextgisweb.vector_layer import VectorLayer

from qgis_headless import CRS, Layer

from ..model import (
    _GEOM_TYPE_TO_QGIS,
    QgisRasterStyle,
    QgisStyleFormat,
    QgisVectorStyle,
    _read_style,
)


@pytest.mark.parametrize(
    "symbolizer, geometry_type",
    (
        pytest.param(sldm.PointSymbolizer(sldm.Graphic()), "POINT", id="point"),
        pytest.param(sldm.LineSymbolizer(sldm.Stroke()), "LINESTRING", id="line"),
        pytest.param(sldm.PolygonSymbolizer(), "POLYGON", id="polygon"),
    ),
)
def test_sld_minimal_vector(symbolizer, geometry_type):
    sld_style = sldm.Style(rules=[sldm.Rule(symbolizers=[symbolizer])])
    sld = sldm.SLD(value=sld_style)

    res = QgisVectorStyle(
        parent=VectorLayer(geometry_type=geometry_type),
        qgis_format=QgisStyleFormat.SLD,
        qgis_sld=sld,
    )

    _read_style(res)


def test_sld_minimal_raster():
    symbolizer = sldm.RasterSymbolizer(channels=sldm.Channels())
    sld_style = sldm.Style(rules=[sldm.Rule(symbolizers=[symbolizer])])
    sld = sldm.SLD(value=sld_style)

    res = QgisRasterStyle(qgis_format=QgisStyleFormat.SLD, qgis_sld=sld)

    _read_style(res)


@pytest.mark.parametrize(
    "geom_type, geom_wkt, geom_symbolizer",
    (
        (
            "POINT",
            "POINT (0 0)",
            sldm.PointSymbolizer(
                graphic=sldm.Graphic(mark=sldm.Mark(fill=sldm.Fill(color="#00FF00")))
            ),
        ),
        # TODO: Fix linestring labels
        # (
        #     "LINESTRING",
        #     "LINESTRING (-90 0,90 0)",
        #     sldm.LineSymbolizer(stroke=sldm.Stroke(color="#00FF00")),
        # ),
        (
            "POLYGON",
            "POLYGON ((-90 -45,-90 45,90 45,90 -45,-90 -45))",
            sldm.PolygonSymbolizer(fill=sldm.Fill(color="#00FF00")),
        ),
    ),
)
def test_sld_text(geom_type, geom_wkt, geom_symbolizer, ngw_env):
    ngw_env.qgis.qgis_init()

    text_symbolizer = sldm.TextSymbolizer(field="label", fill=sldm.Fill(color="#FF0000"))
    sld_style = sldm.Style(
        rules=[
            sldm.Rule(symbolizers=[geom_symbolizer]),
            sldm.Rule(symbolizers=[text_symbolizer]),
        ]
    )
    sld = sldm.SLD(value=sld_style)

    res = QgisVectorStyle(
        parent=VectorLayer(geometry_type=geom_type),
        qgis_format=QgisStyleFormat.SLD,
        qgis_sld=sld,
    )

    style = _read_style(res)

    crs = CRS.from_epsg(4326)

    feature = (1, Geometry.from_wkt(geom_wkt).wkb, ("LABEL",))
    layer = Layer.from_data(
        _GEOM_TYPE_TO_QGIS[geom_type],
        crs,
        (("label", Layer.FT_STRING),),
        (feature,),
    )

    img = render_vector(layer, style, (-180, -90, 180, 90), crs=crs)
    stat = image_stat(img)

    assert stat.green.max == 255, "Geometry missing"
    assert stat.red.max == 255, "Label missing"


def _offset_params():
    offset = 20
    for offset_x, side_x in (
        (-offset, "left"),
        (0, "center"),
        (offset, "right"),
    ):
        for offset_y, side_y in (
            (-offset, "top"),
            (0, "center"),
            (offset, "bottom"),
        ):
            yield pytest.param(offset_x, offset_y, side_x, side_y, id=f"offset-{side_x}-{side_y}")


@pytest.mark.parametrize("offset_x, offset_y, side_x, side_y", _offset_params())
def test_sld_text_offset(ngw_env, offset_x, offset_y, side_x, side_y):
    ngw_env.qgis.qgis_init()

    text_symbolizer = sldm.TextSymbolizer(
        field="label",
        fill=sldm.Fill(color="#FF0000"),
        font_size=16,
        placement=sldm.PointPlacement(offset=[offset_x, offset_y]),
    )
    geom_symbolizer = sldm.PointSymbolizer(
        graphic=sldm.Graphic(mark=sldm.Mark(fill=sldm.Fill(opacity=0)))
    )
    sld = sldm.SLD(
        value=sldm.Style(
            rules=[
                sldm.Rule(symbolizers=[geom_symbolizer]),
                sldm.Rule(symbolizers=[text_symbolizer]),
            ]
        )
    )

    res = QgisVectorStyle(
        parent=VectorLayer(geometry_type="POINT"),
        qgis_format=QgisStyleFormat.SLD,
        qgis_sld=sld,
    )

    style = _read_style(res)

    crs = CRS.from_epsg(4326)

    feature = (1, Geometry.from_wkt("POINT (0 0)").wkb, ("W",))
    layer = Layer.from_data(
        Layer.GT_POINT,
        crs,
        (("label", Layer.FT_STRING),),
        (feature,),
    )

    img = render_vector(layer, style, (-180, -90, 180, 90), crs=crs)

    for (part_x, part_y), (dx, dy) in (
        (("left", "top"), (0, 0)),
        (("right", "top"), (128, 0)),
        (("left", "bottom"), (0, 128)),
        (("right", "bottom"), (128, 128)),
    ):
        img2 = img.crop((0 + dx, 0 + dy, 128 + dx, 128 + dy))
        stat = image_stat(img2)

        exists = (side_x == "center" or (part_x == side_x)) and (
            side_y == "center" or (part_y == side_y)
        )

        if exists:
            assert stat.red.max == 255, "Label missing"
        else:
            assert stat.red.max == 0, "Label exists"


def test_sld_text_halo(ngw_env):
    ngw_env.qgis.qgis_init()

    text_symbolizer = sldm.TextSymbolizer(
        field="label",
        fill=sldm.Fill(color="#FF0000"),
        font_size=12,
        halo=sldm.Halo(radius=3, fill=sldm.Fill(color="#00FF00")),
    )
    geom_symbolizer = sldm.PointSymbolizer(
        graphic=sldm.Graphic(mark=sldm.Mark(fill=sldm.Fill(opacity=0)))
    )
    sld = sldm.SLD(
        value=sldm.Style(
            rules=[
                sldm.Rule(symbolizers=[geom_symbolizer]),
                sldm.Rule(symbolizers=[text_symbolizer]),
            ]
        )
    )

    res = QgisVectorStyle(
        parent=VectorLayer(geometry_type="POINT"),
        qgis_format=QgisStyleFormat.SLD,
        qgis_sld=sld,
    )

    style = _read_style(res)

    crs = CRS.from_epsg(4326)

    feature = (1, Geometry.from_wkt("POINT (0 0)").wkb, ("LABEL",))
    layer = Layer.from_data(
        Layer.GT_POINT,
        crs,
        (("label", Layer.FT_STRING),),
        (feature,),
    )

    img = render_vector(layer, style, (-180, -90, 180, 90), crs=crs)
    stat = image_stat(img)

    assert stat.red.max == 255, "Label missing"
    assert stat.green.max == 255, "Halo missing"
