# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

from pyramid.response import FileResponse

from nextgisweb.env import env
from nextgisweb.resource import resource_factory, ResourceScope

from .model import QgisVectorStyle


def vector_style_qml(request):
    request.resource_permission(ResourceScope.read)

    fn = env.file_storage.filename(request.context.qml_fileobj)

    return FileResponse(fn, request=request)


def setup_pyramid(comp, config):
    config.add_route(
        'qgis.vector_style_qml', '/api/resource/{id}/qml',
        factory=resource_factory
    ).add_view(vector_style_qml, context=QgisVectorStyle, request_method='GET')
