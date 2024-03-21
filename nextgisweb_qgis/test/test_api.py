from pathlib import Path
from secrets import token_hex

import pytest
import transaction

from nextgisweb.env import DBSession

from nextgisweb.raster_layer import RasterLayer
from nextgisweb.spatial_ref_sys import SRS
from nextgisweb.vector_layer import VectorLayer

import nextgisweb_qgis

from ..model import QgisRasterStyle, QgisStyleFormat, QgisVectorStyle

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


@pytest.mark.parametrize(
    "style, status",
    (
        pytest.param("invalid.qml", 422, id="invalid-qml"),
        pytest.param("raster/rounds.qml", 422, id="wrong-layer-type"),
        pytest.param("point-style.qml", 422, id="wrong-geometry-type"),
        pytest.param("landuse/landuse.qml", 201, id="valid-style"),
    ),
)
def test_qgis_vector_style(test_data, style, status, polygon_layer_id, ngw_webtest_app):
    style_data = (test_data / style).read_bytes()
    resp = ngw_webtest_app.put("/api/component/file_upload/", style_data)

    body = dict(
        resource=dict(
            cls="qgis_vector_style",
            parent=dict(id=polygon_layer_id),
            display_name=token_hex(8),
        ),
        qgis_vector_style=dict(file_upload=resp.json),
    )
    resp = ngw_webtest_app.post_json("/api/resource/", body, status=status)

    if status != 201:
        return

    res = QgisVectorStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    req = res.render_request(srs)
    req.render_tile((0, 0, 0), 256)


@pytest.fixture(scope="module")
def raster_layer_id(test_data, ngw_env):
    with transaction.manager:
        layer = RasterLayer().persist()
        layer.load_file(str(test_data / "raster/rounds.tif"))

    yield layer.id


@pytest.mark.parametrize(
    "style, status",
    (
        pytest.param("invalid.qml", 422, id="invalid-qml"),
        pytest.param("landuse/landuse.qml", 422, id="wrong-layer-type"),
        pytest.param("raster/rounds.qml", 201, id="valid-style"),
    ),
)
def test_qgis_raster_style(test_data, style, status, raster_layer_id, ngw_webtest_app):
    style_data = (test_data / style).read_bytes()
    resp = ngw_webtest_app.put("/api/component/file_upload/", style_data)

    body = dict(
        resource=dict(
            cls="qgis_raster_style",
            parent=dict(id=raster_layer_id),
            display_name=token_hex(8),
        ),
        qgis_raster_style=dict(file_upload=resp.json),
    )
    resp = ngw_webtest_app.post_json("/api/resource/", body, status=status)

    if status != 201:
        return

    res = QgisRasterStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    req = res.render_request(srs)
    req.render_tile((0, 0, 0), 256)


@pytest.mark.parametrize(
    "style, format_, expected",
    (
        # QML
        ("contour/rgb.qml", "qml_file", "qml_file"),
        ("contour/rgb.qml", None, "qml_file"),
        ("contour/rgb.qml", "default", None),
        ("contour/rgb.qml", "sld_file", None),
        # SLD
        ("contour/red.sld", "sld_file", "sld_file"),
        ("contour/red.sld", None, "sld_file"),
        ("contour/red.sld", "default", None),
        ("contour/red.sld", "qml_file", None),
        # Default
        (None, "default", "default"),
        (None, None, "default"),
        (None, "qml_file", None),
        (None, "sld_file", None),
    ),
)
def test_format(style, format_, expected, test_data, contour_layer_id, ngw_webtest_app):
    body = dict(
        resource=dict(
            cls="qgis_vector_style",
            parent=dict(id=contour_layer_id),
            display_name=token_hex(8),
        ),
    )
    if format_ is not None or style is not None:
        body["qgis_vector_style"] = dict()
        if format_ is not None:
            body["qgis_vector_style"]["format"] = format_
        if style is not None:
            style_data = (test_data / style).read_bytes()
            resp = ngw_webtest_app.put("/api/component/file_upload/", style_data)
            body["qgis_vector_style"]["file_upload"] = resp.json

    resp = ngw_webtest_app.post_json("/api/resource/", body, status="*")
    if expected is None:
        assert resp.status_code == 422
        return

    qgis_style = QgisVectorStyle.filter_by(id=resp.json["id"]).one()
    assert qgis_style.qgis_format.value == expected


def test_sld_vector(point_layer_id, ngw_webtest_app):
    symbolizer = dict(
        type="point",
        graphic=dict(
            opacity=0.75,
            mark=dict(
                well_known_name="square",
                fill=dict(opacity=0.25, color="#00FF00"),
                stroke=dict(opacity=0.75, color="#FF0000", width=2),
            ),
            size=16,
        ),
    )
    sld = dict(rules=[dict(symbolizers=[symbolizer])])

    resp = ngw_webtest_app.post_json(
        "/api/resource/",
        dict(
            resource=dict(
                cls="qgis_vector_style",
                parent=dict(id=point_layer_id),
                display_name=token_hex(8),
            ),
            qgis_vector_style=dict(format=QgisStyleFormat.SLD.value, sld=sld),
        ),
        status=201,
    )

    res = QgisVectorStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    req = res.render_request(srs)
    img = req.render_tile((0, 0, 0), 256)

    pixel = img.getpixel((128, 128))
    assert pixel == (0, 255, 0, 63)


def test_sld_raster(raster_layer_id, ngw_webtest_app):
    symbolizer = dict(
        type="raster",
        opacity=0.5,
        channels=dict(
            red=dict(source_channel=1),
            green=dict(source_channel=2),
        ),
    )
    sld = dict(rules=[dict(symbolizers=[symbolizer])])

    resp = ngw_webtest_app.post_json(
        "/api/resource/",
        dict(
            resource=dict(
                cls="qgis_raster_style",
                parent=dict(id=raster_layer_id),
                display_name=token_hex(8),
            ),
            qgis_raster_style=dict(format=QgisStyleFormat.SLD.value, sld=sld),
        ),
        status=201,
    )

    res = QgisRasterStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    req = res.render_request(srs)

    for (x, y), color in (
        ((1090690, 6614045), (255, 0, 0, 127)),
        ((4596481, 6491394), (0, 255, 0, 127)),
        ((1158830, 3377406), (0, 0, 0)),
    ):
        extent = (x - 10, y - 10, x + 10, y + 10)
        img = req.render_extent(extent, (256, 256))

        pixel = img.getpixel((128, 128))
        assert pixel[:len(color)] == color
