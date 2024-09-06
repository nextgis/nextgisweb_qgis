import re
from hashlib import md5
from random import Random

from lxml import etree
from lxml.builder import ElementMaker

MD5_NULL_HEXDIGEST = "d41d8cd98f00b204e9800998ecf8427e"
NS_SLD = "http://www.opengis.net/sld"


def rand_color(seed=None):
    r = Random(seed)
    return (r.randrange(0, 256, 1), r.randrange(0, 256, 1), r.randrange(0, 256, 1))


def sld_to_qml_raster(xml):
    nsmap = {None: NS_SLD}

    _sld = etree.fromstring(xml)
    _raster_symbolizer = _sld.find(
        "./NamedLayer/UserStyle/FeatureTypeStyle/Rule/RasterSymbolizer", namespaces=nsmap
    )

    E = ElementMaker()
    qml = E.qgis()
    rasterrenderer = E.rasterrenderer()
    qml.append(E.pipe(rasterrenderer))

    rasterrenderer.attrib["type"] = "multibandcolor"
    if (_opacity := _raster_symbolizer.find("./Opacity", namespaces=nsmap)) is not None:
        rasterrenderer.attrib["opacity"] = _opacity.text
    for _channel in _raster_symbolizer.find("./ChannelSelection", namespaces=nsmap):
        tag = etree.QName(_channel).localname
        band = re.sub("Channel$", "", tag).lower()
        rasterrenderer.attrib[f"{band}Band"] = _channel.find(
            "./SourceChannelName", namespaces=nsmap
        ).text

        if (
            _contrast_enhancement := _channel.find("./ContrastEnhancement", namespaces=nsmap)
        ) is not None:
            if (
                _normalize_enhancement := _contrast_enhancement.find(
                    "./NormalizeEnhancement", namespaces=nsmap
                )
            ) is not None:
                contrast_enhancement = E(f"{band}ContrastEnhancement")
                rasterrenderer.append(contrast_enhancement)
                for _vendor_option in _normalize_enhancement.findall(
                    "./VendorOption", namespaces=nsmap
                ):
                    contrast_enhancement.append(
                        E(_vendor_option.attrib["name"], _vendor_option.text)
                    )

    return etree.tostring(qml, encoding="unicode")


def file_md5_hexdigest(file):
    h = md5()
    with open(file, "rb") as f:
        while buf := f.read(4096):
            h.update(buf)
    return h.hexdigest()
