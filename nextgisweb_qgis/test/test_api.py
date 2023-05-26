from pathlib import Path

import pytest
import transaction
from osgeo import ogr

from nextgisweb.auth import User
from nextgisweb.env.model import DBSession
from nextgisweb.raster_layer import RasterLayer
from nextgisweb.spatial_ref_sys import SRS
from nextgisweb.vector_layer.test import create_feature_layer

import nextgisweb_qgis
from ..model import QgisRasterStyle, QgisVectorStyle


@pytest.fixture(scope='module')
def test_data(ngw_env):
    if qgh_path := ngw_env.qgis.options['test.qgis_headless_path']:
        base = Path(qgh_path) / 'qgis_headless'
    else:
        base = Path(nextgisweb_qgis.__file__).parent.parent / 'qgis_headless'
    data_path = base / 'qgis_headless' / 'test' / 'data'
    if not data_path.is_dir():
        pytest.skip("Test data not found")
    return data_path


@pytest.fixture(scope='module')
def polygon_layer_id(test_data, ngw_resource_group):
    data_polygon = test_data / 'landuse/landuse.geojson'
    ds = ogr.Open(str(data_polygon))
    ogrlayer = ds.GetLayer(0)

    with create_feature_layer(ogrlayer, ngw_resource_group) as layer:
        yield layer.id


@pytest.mark.parametrize('style, status', (
    pytest.param('invalid.qml', 422, id='invalid-qml'),
    pytest.param('raster/rounds.qml', 422, id='wrong-layer-type'),
    pytest.param('point-style.qml', 422, id='wrong-geometry-type'),
    pytest.param('landuse/landuse.qml', 201, id='valid-style'),
))
def test_qgis_vector_style(
    test_data, style, status, polygon_layer_id,
    ngw_webtest_app, ngw_auth_administrator,
):
    style_data = (test_data / style).read_bytes()
    resp = ngw_webtest_app.put('/api/component/file_upload/', style_data)

    body = dict(
        resource=dict(
            cls='qgis_vector_style',
            parent=dict(id=polygon_layer_id),
            display_name='QGIS vector style (test)'
        ),
        qgis_vector_style=dict(file_upload=resp.json)
    )
    resp = ngw_webtest_app.post_json('/api/resource/', body, status=status)

    if status != 201:
        return

    res = QgisVectorStyle.filter_by(id=resp.json['id']).one()
    srs = SRS.filter_by(id=3857).one()
    req = res.render_request(srs)
    req.render_tile((0, 0, 0), 256)

    with transaction.manager:
        DBSession.delete(res)


@pytest.fixture(scope='module')
def raster_layer_id(test_data, ngw_env, ngw_resource_group):
    with transaction.manager:
        layer = RasterLayer(
            parent_id=ngw_resource_group,
            display_name='Test raster layer',
            owner_user=User.by_keyname('administrator'),
            srs=SRS.filter_by(id=3857).one(),
        ).persist()

        layer.load_file(str(test_data / 'raster/rounds.tif'), ngw_env)

    yield layer.id

    with transaction.manager:
        DBSession.delete(RasterLayer.filter_by(id=layer.id).one())


@pytest.mark.parametrize('style, status', (
    pytest.param('invalid.qml', 422, id='invalid-qml'),
    pytest.param('landuse/landuse.qml', 422, id='wrong-layer-type'),
    pytest.param('raster/rounds.qml', 201, id='valid-style'),
))
def test_qgis_raster_style(
    test_data, style, status, raster_layer_id,
    ngw_webtest_app, ngw_auth_administrator,
):
    style_data = (test_data / style).read_bytes()
    resp = ngw_webtest_app.put('/api/component/file_upload/', style_data)

    body = dict(
        resource=dict(
            cls='qgis_raster_style',
            parent=dict(id=raster_layer_id),
            display_name='QGIS raster style (test)'
        ),
        qgis_raster_style=dict(file_upload=resp.json)
    )
    resp = ngw_webtest_app.post_json('/api/resource/', body, status=status)

    if status != 201:
        return

    res = QgisRasterStyle.filter_by(id=resp.json['id']).one()
    srs = SRS.filter_by(id=3857).one()
    req = res.render_request(srs)
    req.render_tile((0, 0, 0), 256)

    with transaction.manager:
        DBSession.delete(res)
