from PIL import Image

from nextgisweb.i18n import trstring_factory

COMP_ID = 'qgis'
_ = trstring_factory(COMP_ID)


def qgis_image_to_pil(src):
    return Image.frombytes('RGBA', src.size(), src.to_bytes().tobytes(), 'raw')
