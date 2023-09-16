from enum import Enum

from pyramid.response import FileResponse, Response

from nextgisweb.env import gettext

from nextgisweb.core.exception import ValidationError
from nextgisweb.resource import ResourceScope, resource_factory

from .model import QgisRasterStyle, QgisStyleFormat, QgisVectorStyle, read_style


class OriginalEnum(Enum):
    PREFER = "prefer"
    REQUIRE = "require"
    PROCESS = "process"


def style_qml(
    resource,
    request,
    *,
    original: OriginalEnum = OriginalEnum.PREFER,
):
    """Read style in QML format"""
    request.resource_permission(ResourceScope.read)

    if (original == OriginalEnum.PROCESS) or (
        original == OriginalEnum.PREFER and resource.qgis_format != QgisStyleFormat.QML_FILE
    ):
        style = read_style(resource)
        response = Response(style.to_string(), request=request)
    elif resource.qgis_format == QgisStyleFormat.QML_FILE:
        fn = request.env.file_storage.filename(resource.qgis_fileobj)
        response = FileResponse(fn, request=request)
    else:
        raise ValidationError(
            message=gettext(
                "The original QML was requested but the style has '{}' format. "
                "Use other values of the 'original' parameter."
            ).format(resource.qgis_format.value)
        )

    response.content_disposition = "attachment; filename=%d.qml" % resource.id
    return response


def setup_pyramid(comp, config):
    route = config.add_route(
        "qgis.style_qml",
        "/api/resource/{id:uint}/qml",
        factory=resource_factory,
        overloaded=True,
    )

    route.add_view(style_qml, context=QgisVectorStyle, request_method="GET")
    route.add_view(style_qml, context=QgisRasterStyle, request_method="GET")
