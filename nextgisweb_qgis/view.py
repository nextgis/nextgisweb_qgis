from nextgisweb.env import DBSession, env

from nextgisweb.jsrealm import jsentry
from nextgisweb.resource import Widget
from nextgisweb.resource.view import resource_sections

from .model import QgisRasterStyle, QgisVectorStyle


class VectorStyleWidget(Widget):
    resource = QgisVectorStyle
    operation = ("create", "update")
    amdmod = jsentry("@nextgisweb/qgis/vector-editor-widget")

    def config(self):
        result = super().config()
        result["geometryType"] = self.obj.parent.geometry_type
        return result


class RasterStyleWidget(Widget):
    resource = QgisRasterStyle
    operation = ("create", "update")
    amdmod = jsentry("@nextgisweb/qgis/raster-editor-widget")

    def config(self):
        result = super().config()
        parent = self.obj.parent
        result["dtype"] = parent.dtype
        result["band_count"] = parent.band_count
        result["parent_id"] = parent.id
        return result


@resource_sections("@nextgisweb/qgis/resource-section/default-style", order=-60)
def resource_section_default_style(obj, *, request, **kwargs):
    if not env.qgis.options["default_style"] or any(
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

        return dict(
            payload=dict(
                resource=dict(
                    cls=cls.identity,
                    parent=dict(id=obj.id),
                    display_name=display_name,
                )
            )
        )


def setup_pyramid(comp, config):
    pass
