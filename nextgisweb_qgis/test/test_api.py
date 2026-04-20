import json
from io import BytesIO

import pytest
import transaction
from PIL import Image
from qgis_headless.util import image_stat

from nextgisweb.pyramid.test import WebTestApp
from nextgisweb.render import RenderPostprocess
from nextgisweb.resource.test import ResourceAPI
from nextgisweb.spatial_ref_sys import SRS
from nextgisweb.vector_layer.model import VectorLayer

from ..model import QgisRasterStyle, QgisStyleFormat, QgisVectorStyle

pytestmark = pytest.mark.usefixtures("ngw_resource_defaults", "ngw_auth_administrator")


@pytest.mark.parametrize(
    "style, status",
    (
        pytest.param("invalid.qml", 422, id="invalid-qml"),
        pytest.param("raster/rounds.qml", 422, id="wrong-layer-type"),
        pytest.param("point-style.qml", 422, id="wrong-geometry-type"),
        pytest.param("landuse/landuse.qml", 201, id="valid-style"),
    ),
)
def test_qgis_vector_style(test_data, style, status, polygon_layer_id, ngw_file_upload):
    rapi = ResourceAPI()

    style_fu = ngw_file_upload(test_data / style)

    resp = rapi.create_request(
        "qgis_vector_style",
        {
            "resource": {"parent": {"id": polygon_layer_id}},
            "qgis_vector_style": {"file_upload": style_fu},
        },
        status=status,
    )

    if status != 201:
        return

    res = QgisVectorStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    req = res.render_request(srs)
    req.render_tile((0, 0, 0), 256)


@pytest.mark.parametrize(
    "style, status",
    (
        pytest.param("invalid.qml", 422, id="invalid-qml"),
        pytest.param("landuse/landuse.qml", 422, id="wrong-layer-type"),
        pytest.param("raster/rounds.qml", 201, id="valid-style"),
    ),
)
def test_qgis_raster_style(test_data, style, status, raster_layer_id, ngw_file_upload):
    rapi = ResourceAPI()

    style_fu = ngw_file_upload(test_data / style)

    resp = rapi.create_request(
        "qgis_raster_style",
        {
            "resource": {"parent": {"id": raster_layer_id}},
            "qgis_raster_style": {"file_upload": style_fu},
        },
        status=status,
    )

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
def test_format(style, format_, expected, test_data, contour_layer_id, ngw_file_upload):
    rapi = ResourceAPI()

    body = {"resource": {"parent": {"id": contour_layer_id}}}
    if format_ is not None or style is not None:
        body["qgis_vector_style"] = {}
        if format_ is not None:
            body["qgis_vector_style"]["format"] = format_
        if style is not None:
            style_fu = ngw_file_upload(test_data / style)
            body["qgis_vector_style"]["file_upload"] = style_fu

    resp = rapi.create_request("qgis_vector_style", body, status="*")

    if expected is None:
        assert resp.status_code == 422
        return

    assert resp.status_code // 100 == 2
    qgis_style = QgisVectorStyle.filter_by(id=resp.json["id"]).one()
    assert qgis_style.qgis_format.value == expected


def test_sld_vector(point_layer_id):
    rapi = ResourceAPI()

    symbolizer = {
        "type": "point",
        "graphic": {
            "opacity": 0.75,
            "mark": {
                "well_known_name": "square",
                "fill": {"opacity": 0.25, "color": "#00FF00"},
                "stroke": {"opacity": 0.75, "color": "#FF0000", "width": 2},
            },
            "size": 16,
        },
    }

    sld = {"rules": [{"symbolizers": [symbolizer]}]}

    resp = rapi.create_request(
        "qgis_vector_style",
        {
            "resource": {"parent": {"id": point_layer_id}},
            "qgis_vector_style": {"format": QgisStyleFormat.SLD.value, "sld": sld},
        },
        status=201,
    )

    res = QgisVectorStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    req = res.render_request(srs)
    img = req.render_tile((0, 0, 0), 256)

    pixel = img.getpixel((128, 128))
    assert pixel == (0, 255, 0, 63)


def test_sld_raster(raster_layer_id):
    rapi = ResourceAPI()

    symbolizer = {
        "type": "raster",
        "opacity": 0.5,
        "channels": {
            "red": {"source_channel": 1},
            "green": {"source_channel": 2},
        },
    }

    sld = {"rules": [{"symbolizers": [symbolizer]}]}

    resp = rapi.create_request(
        "qgis_raster_style",
        {
            "resource": {"parent": {"id": raster_layer_id}},
            "qgis_raster_style": {"format": QgisStyleFormat.SLD.value, "sld": sld},
        },
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
        assert pixel[: len(color)] == color


def test_qgis_raster_style_render_request_postprocess(test_data, raster_layer_id, ngw_file_upload):
    rapi = ResourceAPI()

    style_fu = ngw_file_upload(test_data / "raster/rounds.qml")
    resp = rapi.create_request(
        "qgis_raster_style",
        {
            "resource": {"parent": {"id": raster_layer_id}},
            "qgis_raster_style": {"file_upload": style_fu},
        },
        status=201,
    )

    res = QgisRasterStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    postprocess = RenderPostprocess(contrast=1.1)

    req = res.render_request(srs, cond={"postprocess": postprocess})

    assert req.params["postprocess"] == postprocess


def test_qgis_raster_render_tile_applies_postprocess_on_padded_extent(
    test_data,
    raster_layer_id,
    ngw_file_upload,
    monkeypatch,
):
    rapi = ResourceAPI()

    style_fu = ngw_file_upload(test_data / "raster/rounds.qml")
    resp = rapi.create_request(
        "qgis_raster_style",
        {
            "resource": {"parent": {"id": raster_layer_id}},
            "qgis_raster_style": {"file_upload": style_fu},
        },
        status=201,
    )

    res = QgisRasterStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    tile = (0, 0, 0)
    captured = {}

    def fake_apply_postprocess(img, postprocess, *, extent):
        captured["size"] = img.size
        captured["extent"] = extent
        captured["postprocess"] = postprocess
        return img

    monkeypatch.setattr("nextgisweb_qgis.model.apply_postprocess", fake_apply_postprocess)

    req = res.render_request(srs, cond={"postprocess": RenderPostprocess(contrast=1.1)})
    img = req.render_tile(tile, 256)

    tile_extent = srs.tile_extent(tile)

    assert img is not None
    assert img.size == (256, 256)
    assert captured["size"] == (384, 384)
    assert captured["extent"] == pytest.approx(
        (
            tile_extent[0] - (tile_extent[2] - tile_extent[0]) / 4,
            tile_extent[1] - (tile_extent[3] - tile_extent[1]) / 4,
            tile_extent[2] + (tile_extent[2] - tile_extent[0]) / 4,
            tile_extent[3] + (tile_extent[3] - tile_extent[1]) / 4,
        )
    )
    assert captured["postprocess"].contrast == 1.1


def test_qgis_raster_render_extent_applies_postprocess_on_padded_extent(
    test_data,
    raster_layer_id,
    ngw_file_upload,
    monkeypatch,
):
    rapi = ResourceAPI()

    style_fu = ngw_file_upload(test_data / "raster/rounds.qml")
    resp = rapi.create_request(
        "qgis_raster_style",
        {
            "resource": {"parent": {"id": raster_layer_id}},
            "qgis_raster_style": {"file_upload": style_fu},
        },
        status=201,
    )

    res = QgisRasterStyle.filter_by(id=resp.json["id"]).one()
    srs = SRS.filter_by(id=3857).one()
    extent = (0.0, 0.0, 256.0, 256.0)
    captured = {}

    def fake_apply_postprocess(img, postprocess, *, extent):
        captured["size"] = img.size
        captured["extent"] = extent
        captured["postprocess"] = postprocess
        return img

    monkeypatch.setattr("nextgisweb_qgis.model.apply_postprocess", fake_apply_postprocess)

    req = res.render_request(srs, cond={"postprocess": RenderPostprocess(contrast=1.1)})
    img = req.render_extent(extent, (256, 256))

    assert img is not None
    assert img.size == (256, 256)
    assert captured["size"] == (384, 384)
    assert captured["extent"] == pytest.approx((-64.0, -64.0, 320.0, 320.0))
    assert captured["postprocess"].contrast == 1.1


@pytest.fixture(scope="module")
def two_point_style_id(two_point_layer_id, ngw_data_path):
    with transaction.manager:
        layer = VectorLayer.filter_by(id=two_point_layer_id).one()
        style = QgisVectorStyle(parent=layer).from_file(ngw_data_path / "two-points.qml").persist()
    yield style.id


@pytest.mark.parametrize(
    "feature_filter, color_max",
    (
        pytest.param(None, (255, 255, 0, 255), id="both"),
        pytest.param(["all", ["==", ["get", "color"], "#FF0000"]], (255, 0, 0, 255), id="red"),
        pytest.param(["all", ["==", ["get", "color"], "#00FF00"]], (0, 255, 0, 255), id="green"),
        pytest.param(["all", ["==", ["get", "color"], "no-match"]], (0, 0, 0, 0), id="empty"),
    ),
)
def test_feature_filter(
    feature_filter, color_max, two_point_style_id, ngw_webtest_app: WebTestApp
):
    query = dict(
        resource=two_point_style_id,
        extent="-20037508,-20037508,20037508,20037508",
        size="256,256",
        nd=200,
    )
    if feature_filter is not None:
        query[f"filter[{two_point_style_id}]"] = json.dumps(feature_filter)

    resp = ngw_webtest_app.get("/api/component/render/image", query=query, status=200)
    im = Image.open(BytesIO(resp.body))
    stat = image_stat(im)

    r, g, b, a = color_max
    assert stat.red.max == r
    assert stat.green.max == g
    assert stat.blue.max == b
    assert stat.alpha.max == a
