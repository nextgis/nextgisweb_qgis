from typing import Any

from nextgisweb.env import DBSession, inject

from nextgisweb.feature_layer import FeatureLayerMixin
from nextgisweb.jsrealm import jsentry
from nextgisweb.pyramid.tomb import Request
from nextgisweb.raster_layer import RasterLayer
from nextgisweb.resource import Resource, Widget
from nextgisweb.resource.view import resource_sections

from .component import QgisComponent
from .model import QgisRasterStyle, QgisVectorStyle


class VectorStyleWidget(Widget):
    resource = QgisVectorStyle
    operation = ("create", "update")
    amdmod = jsentry("@nextgisweb/qgis/vector-editor-widget")

    def config(self) -> dict:
        result = super().config()
        parent = self.obj.parent
        assert isinstance(parent, FeatureLayerMixin)
        result["geometryType"] = parent.geometry_type
        return result


class RasterStyleWidget(Widget):
    resource = QgisRasterStyle
    operation = ("create", "update")
    amdmod = jsentry("@nextgisweb/qgis/raster-editor-widget")

    def config(self) -> dict:
        result = super().config()
        parent = self.obj.parent
        assert isinstance(parent, RasterLayer)
        result["dtype"] = parent.dtype
        result["band_count"] = parent.band_count
        result["parent_id"] = parent.id
        return result


@resource_sections("@nextgisweb/qgis/resource-section/default-style", order=-60)
@inject()
def resource_section_default_style(
    obj: Resource, *, request: Request, qgis: QgisComponent = inject.arg(), **kwargs: Any
) -> dict | None:
    if not qgis.options["default_style"] or any(
        child.cls.endswith("_style") for child in obj.children
    ):
        return

    for cls in (QgisVectorStyle, QgisRasterStyle):
        if not cls.check_parent(obj):
            continue

        with DBSession.no_autoflush:
            child = cls(parent=obj, owner_user=request.user)
            display_name = child.suggest_display_name(request.localizer.translate)
            child.parent = None

        return {
            "payload": {
                "resource": {
                    "cls": cls.identity,
                    "parent": {"id": obj.id},
                    "display_name": display_name,
                }
            }
        }
