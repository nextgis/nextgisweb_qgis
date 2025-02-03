import pytest

from nextgisweb.vector_layer import VectorLayer

from ..model import QgisStyleFormat, QgisVectorStyle, update_not_modified

pytestmark = pytest.mark.usefixtures("ngw_resource_defaults", "ngw_auth_administrator")


def test_update_not_modified(point_layer_id, test_data, ngw_txn):
    vl = VectorLayer.filter_by(id=point_layer_id).one()
    qvs = QgisVectorStyle(parent=vl).persist()

    qml1 = test_data / "zero" / "red-circle.qml"
    qml2 = test_data / "zero" / "marker.qml"

    assert update_not_modified(qvs, qml1, "qgis.test")
    assert update_not_modified(qvs, qml2, "qgis.test")

    fileobj2 = qvs.qgis_fileobj
    digest2 = qvs.resmeta[0].value

    assert qvs.resmeta[0].key == "qgis.test"
    assert digest2

    qvs.qgis_format = QgisStyleFormat.DEFAULT
    qvs.qgis_fileobj = None

    assert not update_not_modified(qvs, qml2, "qgis.test")

    qvs.qgis_format = QgisStyleFormat.QML_FILE
    qvs.qgis_fileobj = fileobj2

    assert update_not_modified(qvs, qml2, "qgis.test")
    assert qvs.resmeta[0].value == digest2

    assert update_not_modified(qvs, qml1, "qgis.test")
    assert qvs.resmeta[0].value != digest2

    qvs.resmeta[:] = []
    assert not update_not_modified(qvs, qml1, "qgis.test")


def test_scale_range(point_layer_id, test_data, ngw_txn):
    vl = VectorLayer.filter_by(id=point_layer_id).one()
    qvs = QgisVectorStyle(parent=vl).from_file(test_data / "scale/100_10.qml").persist()

    assert qvs.qgis_scale_range_cache is None

    ngw_txn.commit()

    qvs = QgisVectorStyle.filter_by(id=qvs.id).one()
    sr_cache = qvs.qgis_scale_range_cache
    assert sr_cache is not None
    assert sr_cache.min_scale_denom == 100000
    assert sr_cache.max_scale_denom == 10000
