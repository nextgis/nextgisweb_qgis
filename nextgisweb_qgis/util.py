import re
from hashlib import md5
from random import Random

from lxml import etree
from lxml.builder import ElementMaker

from nextgisweb.sld import NSMAP as nsmap_sld

MD5_NULL_HEXDIGEST = "d41d8cd98f00b204e9800998ecf8427e"


def rand_color(seed=None):
    r = Random(seed)
    return (r.randrange(0, 256, 1), r.randrange(0, 256, 1), r.randrange(0, 256, 1))


def sld_find(el, path):
    return el.find(path, namespaces=nsmap_sld)


def sld_to_qml_raster(xml):
    _sld = etree.fromstring(xml)
    _raster_symbolizer = sld_find(
        _sld, "./NamedLayer/UserStyle/se:FeatureTypeStyle/se:Rule/se:RasterSymbolizer"
    )

    E = ElementMaker()
    qml = E.qgis()
    rasterrenderer = E.rasterrenderer()
    qml.append(E.pipe(rasterrenderer))

    rasterrenderer.attrib["type"] = "multibandcolor"
    if (_opacity := sld_find(_raster_symbolizer, "./se:Opacity")) is not None:
        rasterrenderer.attrib["opacity"] = _opacity.text
    for _channel in sld_find(_raster_symbolizer, "./se:ChannelSelection"):
        tag = etree.QName(_channel).localname
        band = re.sub("Channel$", "", tag).lower()
        rasterrenderer.attrib[f"{band}Band"] = sld_find(_channel, "./se:SourceChannelName").text

        if (_ce := sld_find(_channel, "./se:ContrastEnhancement")) is not None:
            if (_normalize := sld_find(_ce, "./se:Normalize")) is not None:
                contrast_enhancement = E(f"{band}ContrastEnhancement")
                rasterrenderer.append(contrast_enhancement)
                for _vendor_option in _normalize.findall("./VendorOption"):
                    contrast_enhancement.append(
                        E(_vendor_option.attrib["name"], _vendor_option.text)
                    )

    return etree.tostring(qml, encoding="unicode")


def sld_fix_vector(xml):
    fixed = False

    _sld = etree.fromstring(xml)
    E = ElementMaker(namespace=nsmap_sld["se"])
    for _rule in sld_find(_sld, "./NamedLayer/UserStyle/se:FeatureTypeStyle/se:Rule"):
        match etree.QName(_rule).localname:
            case "PointSymbolizer":
                _graphic = sld_find(_rule, "./se:Graphic")
                if _graphic is None:
                    _graphic = E.Graphic()
                    _rule.append(_graphic)
                if len(_graphic) == 0:
                    fixed = True
                    _graphic.append(E.Mark())
            case "PolygonSymbolizer":
                if len(_rule) == 0:
                    fixed = True
                    _rule.append(E.Stroke())

    if fixed:
        xml = etree.tostring(_sld, encoding="unicode")

    return xml


def file_md5_hexdigest(file):
    h = md5()
    with open(file, "rb") as f:
        while buf := f.read(4096):
            h.update(buf)
    return h.hexdigest()
