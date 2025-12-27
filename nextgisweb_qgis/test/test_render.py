from pathlib import Path

import pytest
from qgis_headless.util import image_stat

from nextgisweb.vector_layer import VectorLayer

from ..model import QgisVectorStyle

pytestmark = pytest.mark.usefixtures("ngw_resource_defaults")


@pytest.fixture()
def pad_req():
    data_path = Path(__file__).parent / "data"
    vl = VectorLayer().persist().from_ogr(data_path / "center-west.geojson")
    style = QgisVectorStyle(parent=vl).from_file(data_path / "circle-d256.qml").persist()
    style.qgis_fileobj_id = -1  # for cache reading
    return style.render_request(vl.srs)


@pytest.mark.parametrize(
    "tile, color",
    (
        pytest.param((1, 0, 0), (0, 0, 255, 255), id="zoom-1-in-tile"),
        pytest.param((1, 1, 0), (0, 0, 255, 255), id="zoom-1-near-tile"),
        pytest.param((2, 1, 1), (0, 0, 255, 255), id="zoom-2-in-tile"),
        pytest.param((2, 2, 1), None, id="zoom-2-far-of-tile"),
    ),
)
def test_render_padding(tile, color, pad_req):
    im = pad_req.render_tile(tile, 256)

    if color is None:
        assert im is None
        return

    stat = image_stat(im)
    r, g, b, a = color
    assert stat.alpha.max == a
    assert stat.red.max == r
    assert stat.green.max == g
    assert stat.blue.max == b
