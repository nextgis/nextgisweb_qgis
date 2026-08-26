import re
from hashlib import md5
from random import Random

from lxml import etree
from lxml.builder import ElementMaker

from nextgisweb.core.exception import ValidationError
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
    _fts = sld_find(_sld, "./NamedLayer/UserStyle/se:FeatureTypeStyle")
    for _rule in sld_find(_fts, "./se:Rule"):
        match etree.QName(_rule).localname:
            case "PointSymbolizer":
                _graphic = sld_find(_rule, "./se:Graphic")
                if _graphic is None:
                    _graphic = E.Graphic()
                    _rule.append(_graphic)
                if len(_graphic) == 0:
                    fixed = True
                    _graphic.append(E.Mark())

            case "LineSymbolizer":
                if (_text_symbolizer := sld_find(_fts, "./se:Rule/se:TextSymbolizer")) is not None:
                    _label_placement = sld_find(_text_symbolizer, "./se:LabelPlacement")
                    if _label_placement is None:
                        _label_placement = E.LabelPlacement()
                        _text_symbolizer.append(_label_placement)
                    if len(_label_placement) == 0:
                        fixed = True
                        _label_placement.append(E.PointPlacement())

            case "PolygonSymbolizer":
                if len(_rule) == 0:
                    fixed = True
                    _rule.append(E.Stroke())

    if fixed:
        xml = etree.tostring(_sld, encoding="unicode")

    return xml


def fix_layer_geometry_type(qml_str, geometry_type):
    """Post-process QML to ensure correct layerGeometryType.

    Removes all existing layerGeometryType elements and inserts the correct
    one based on the layer's actual geometry type. This mirrors how QGIS
    Desktop handles missing layerGeometryType, but QGIS Headless requires it
    to be explicit.
    """
    if geometry_type is None:
        return qml_str

    root = etree.fromstring(qml_str.encode("utf-8"))

    for el in root.findall("layerGeometryType"):
        el.getparent().remove(el)

    geom_el = etree.SubElement(root, "layerGeometryType")
    geom_el.text = str(geometry_type)

    return etree.tostring(root, encoding="unicode", xml_declaration=False)


def add_qml_metadata(qml_str, layer_id, prompt):
    """Add layer reference and user prompt to QML metadata for debugging."""
    root = etree.fromstring(qml_str.encode("utf-8"))

    metadata = etree.SubElement(root, "metadata")
    layer_el = etree.SubElement(metadata, "layer_id")
    layer_el.text = str(layer_id)
    prompt_el = etree.SubElement(metadata, "user_prompt")
    prompt_el.text = prompt

    return etree.tostring(root, encoding="unicode", xml_declaration=False)


def validate_qml_structure(qml_str):
    """Validate that QML contains at least one renderer-v2 or labeling tag."""
    root = etree.fromstring(qml_str.encode("utf-8"))
    if root.find("renderer-v2") is None and root.find("labeling") is None:
        raise ValidationError(
            message="Generated QML is invalid: missing renderer-v2 and labeling tags."
        )


def file_md5_hexdigest(file):
    h = md5()
    with open(file, "rb") as f:
        while buf := f.read(4096):
            h.update(buf)
    return h.hexdigest()
