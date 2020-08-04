# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from io import BytesIO

from PIL import Image
import qgis_headless

from nextgisweb.i18n import trstring_factory

COMP_ID = 'qgis'
_ = trstring_factory(COMP_ID)


def qgis_init():
    if not getattr(qgis_init, '_done', False):
        qgis_headless.init([])
        qgis_init._done = True


def qgis_image_to_pil(src):
    return Image.open(BytesIO(src.to_string()))
