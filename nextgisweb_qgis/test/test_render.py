import json
from pathlib import Path

import pytest
from osgeo import gdal
from qgis_headless.util import image_stat

from nextgisweb.env import DBSession

from nextgisweb.raster_layer import RasterLayer, RasterLayerStorage
from nextgisweb.spatial_ref_sys import SRS
from nextgisweb.vector_layer import VectorLayer

from ..model import QgisRasterStyle, QgisVectorStyle

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


def test_render_s3_raster_cache(ngw_raster_layer_s3_storage, test_data, ngw_commit):
    with (
        gdal.config_option("CPL_VSIL_SHOW_NETWORK_STATS", "NO"),
        gdal.config_option("CPL_VSIL_NETWORK_STATS_ENABLED", "YES"),
        gdal.config_option("GDAL_PAM_ENABLED", "NO"),
    ):
        storage = RasterLayerStorage(**ngw_raster_layer_s3_storage).persist()

        layer = RasterLayer(
            srs=SRS.filter_by(id=3857).one(),
            storage=storage,
        ).persist()
        layer.load_file(test_data / "raster" / "sochi-aster-dem.tif")

        style = QgisRasterStyle(parent=layer).persist()
        DBSession.flush()

        extent = (4452779.63, 5311971.85, 4564099.12, 5465442.18)
        size = (256, 256)

        req = style.render_request(layer.srs)

        gdal.VSICurlClearCache()
        gdal.NetworkStatsReset()

        req.render_extent(extent, size)

        stats = json.loads(gdal.NetworkStatsGetAsSerializedJSON())

        vsis3_files = stats["handlers"]["vsis3"]["files"]

        downloaded = sum(
            method.get("downloaded_bytes", 0)
            for file_stats in vsis3_files.values()
            for method in file_stats["methods"].values()
        )

        assert downloaded > 0
        assert stats["methods"]

        # The same render must be served entirely from the GDAL CURL cache
        gdal.NetworkStatsReset()

        req.render_extent(extent, size)
        stats = json.loads(gdal.NetworkStatsGetAsSerializedJSON())
        assert stats["methods"] == {}
