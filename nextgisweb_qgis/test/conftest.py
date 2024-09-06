from pathlib import Path

import pytest
import transaction

from nextgisweb.env import DBSession

from nextgisweb.vector_layer import VectorLayer

import nextgisweb_qgis

pytestmark = pytest.mark.usefixtures("ngw_resource_defaults", "ngw_auth_administrator")


@pytest.fixture(scope="module")
def test_data(ngw_env):
    if qgh_path := ngw_env.qgis.options["test.qgis_headless_path"]:
        base = Path(qgh_path) / "qgis_headless"
    else:
        base = Path(nextgisweb_qgis.__file__).parent.parent / "qgis_headless"
    data_path = base / "qgis_headless" / "test" / "data"
    if not data_path.is_dir():
        pytest.skip("Test data not found")
    return data_path


@pytest.fixture(scope="module")
def point_layer_id(test_data):
    with transaction.manager:
        source = test_data / "zero/data.geojson"
        res = VectorLayer().persist().from_ogr(source)
        DBSession.flush()

    yield res.id


@pytest.fixture(scope="module")
def polygon_layer_id(test_data):
    with transaction.manager:
        source = test_data / "landuse/landuse.geojson"
        res = VectorLayer().persist().from_ogr(source)
        DBSession.flush()

    yield res.id


@pytest.fixture(scope="module")
def contour_layer_id(test_data):
    with transaction.manager:
        source = test_data / "contour/data.geojson"
        res = VectorLayer().persist().from_ogr(source)
        DBSession.flush()

    yield res.id
