# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

from pyramid.response import FileResponse

from nextgisweb.env import env
from nextgisweb.resource import resource_factory, ResourceScope

from .model import QgisVectorStyle


def vector_style_qml(request):
    request.resource_permission(ResourceScope.read)

    fn = env.file_storage.filename(request.context.qml_fileobj)

    response = FileResponse(fn, request=request)
    response.content_disposition = (b'attachment; filename=%d.qml'
                                    % request.context.id)

    return response


def setup_pyramid(comp, config):
    config.add_route(
        'qgis.vector_style_qml', '/api/resource/{id}/qml',
        factory=resource_factory
    ).add_view(vector_style_qml, context=QgisVectorStyle, request_method='GET')
