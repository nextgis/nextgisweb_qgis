import pytest

from nextgisweb.sld import model as sldm
from nextgisweb.vector_layer import VectorLayer

from ..model import QgisRasterStyle, QgisStyleFormat, QgisVectorStyle, _read_style


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
