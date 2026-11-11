import re
from hashlib import md5
from pathlib import Path
from random import Random
from typing import Literal, overload

from lxml import etree
from lxml.builder import ElementMaker
from lxml.etree import Element

from nextgisweb.core.exception import ValidationError
from nextgisweb.sld import NSMAP as nsmap_sld

MD5_NULL_HEXDIGEST = "d41d8cd98f00b204e9800998ecf8427e"


def rand_color(seed: int | None = None) -> tuple[int, int, int]:
    r = Random(seed)
    return (r.randrange(0, 256, 1), r.randrange(0, 256, 1), r.randrange(0, 256, 1))


@overload
def sld_find(el: Element, path: str, *, must: Literal[True]) -> Element: ...


@overload
def sld_find(el: Element, path: str, *, must: Literal[False] = False) -> Element | None: ...


def sld_find(el: Element, path: str, *, must: bool = False) -> Element | None:
    result = el.find(path, namespaces=nsmap_sld)
    if must:
        assert result is not None
    return result


def sld_to_qml_raster(xml: str) -> str:
    _sld = etree.fromstring(xml)
    _raster_symbolizer = sld_find(
        _sld, "./NamedLayer/UserStyle/se:FeatureTypeStyle/se:Rule/se:RasterSymbolizer", must=True
    )

    E = ElementMaker()
    qml = E.qgis()
    rasterrenderer = E.rasterrenderer()
    qml.append(E.pipe(rasterrenderer))

    rasterrenderer.attrib["type"] = "multibandcolor"
    if (_opacity := sld_find(_raster_symbolizer, "./se:Opacity")) is not None:
        assert _opacity.text is not None
        rasterrenderer.attrib["opacity"] = _opacity.text
    for _channel in sld_find(_raster_symbolizer, "./se:ChannelSelection", must=True):
        tag = etree.QName(_channel).localname
        band = re.sub("Channel$", "", tag).lower()
        _channel_name = sld_find(_channel, "./se:SourceChannelName", must=True)
        assert _channel_name.text is not None
        rasterrenderer.attrib[f"{band}Band"] = _channel_name.text

        if (_ce := sld_find(_channel, "./se:ContrastEnhancement")) is not None:
            if (_normalize := sld_find(_ce, "./se:Normalize")) is not None:
                contrast_enhancement = E(f"{band}ContrastEnhancement")
                rasterrenderer.append(contrast_enhancement)
                for _vendor_option in _normalize.findall("./VendorOption"):
                    assert _vendor_option.text is not None
                    contrast_enhancement.append(
                        E(_vendor_option.attrib["name"], _vendor_option.text)
                    )

    return etree.tostring(qml, encoding="unicode")


def sld_fix_vector(xml: str) -> str:
    fixed = False

    _sld = etree.fromstring(xml)
    E = ElementMaker(namespace=nsmap_sld["se"])
    _fts = sld_find(_sld, "./NamedLayer/UserStyle/se:FeatureTypeStyle", must=True)
    for _rule in sld_find(_fts, "./se:Rule", must=True):
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


def fix_layer_geometry_type(qml_str: str, geometry_type: int) -> str:
    """Post-process QML to ensure correct layerGeometryType.

    Removes all existing layerGeometryType elements and inserts the correct
    one based on the layer's actual geometry type. This mirrors how QGIS
    Desktop handles missing layerGeometryType, but QGIS Headless requires it
    to be explicit.
    """
    root = etree.fromstring(qml_str.encode("utf-8"))

    for el in root.findall("layerGeometryType"):
        parent = el.getparent()
        assert parent is not None
        parent.remove(el)

    geom_el = etree.SubElement(root, "layerGeometryType")
    geom_el.text = str(geometry_type)

    return etree.tostring(root, encoding="unicode", xml_declaration=False)  # ty: ignore[invalid-return-type]


def fix_labeling_enabled(qml_str: str) -> str:
    """Post-process QML to keep labelsEnabled consistent with <labeling>.

    QGIS Desktop only renders labels when the root element's labelsEnabled
    attribute is "1", independently of the <labeling> element itself. LLMs
    reliably forget to set it, so it's enforced here instead of relying on
    the prompt.
    """
    root = etree.fromstring(qml_str.encode("utf-8"))
    root.attrib["labelsEnabled"] = "1" if root.find("labeling") is not None else "0"
    return etree.tostring(root, encoding="unicode", xml_declaration=False)  # ty: ignore[invalid-return-type]


def add_qml_metadata(qml_str: str, layer_id: int, prompt: str) -> str:
    """Add layer reference and user prompt to QML metadata for debugging."""
    root = etree.fromstring(qml_str.encode("utf-8"))

    metadata = etree.SubElement(root, "metadata")
    layer_el = etree.SubElement(metadata, "layer_id")
    layer_el.text = str(layer_id)
    prompt_el = etree.SubElement(metadata, "user_prompt")
    prompt_el.text = prompt

    return etree.tostring(root, encoding="unicode", xml_declaration=False)  # ty: ignore[invalid-return-type]


def validate_qml_structure(qml_str: str) -> None:
    """Validate that QML contains at least one renderer-v2 or labeling tag."""
    root = etree.fromstring(qml_str.encode("utf-8"))
    if root.find("renderer-v2") is None and root.find("labeling") is None:
        raise ValidationError(
            message="Generated QML is invalid: missing renderer-v2 and labeling tags."
        )


# QML integer geometry type (see _QML_GEOM_TYPE in api.py) -> name / expected <symbol type="...">
QML_GEOM_TYPE_NAME = {0: "point", 1: "line", 2: "polygon"}
QML_GEOM_TYPE_SYMBOL_TYPE = {0: "marker", 1: "line", 2: "fill"}


def validate_symbol_geometry_type(qml_str: str, geometry_type: int) -> None:
    """Validate that every top-level symbol matches the layer's geometry type.

    The LLM is told the layer's geometry type, but sometimes ignores it and
    generates a symbol for the wrong geometry (e.g. a line symbol for a
    polygon layer). Such styles don't fail to parse, they just don't render
    the way the user asked, so this is checked explicitly instead of trusting
    the prompt.
    """
    expected = QML_GEOM_TYPE_SYMBOL_TYPE.get(geometry_type)
    if expected is None:
        return

    root = etree.fromstring(qml_str.encode("utf-8"))
    for symbol in root.findall("renderer-v2/symbols/symbol"):
        actual = symbol.get("type")
        if actual != expected:
            raise ValidationError(
                message="Generated QML is invalid: layer geometry requires a "
                "'{}' symbol, but generated a '{}' symbol.".format(expected, actual)
            )


def file_md5_hexdigest(file: Path) -> str:
    h = md5()
    with open(file, "rb") as f:
        while buf := f.read(4096):
            h.update(buf)
    return h.hexdigest()
