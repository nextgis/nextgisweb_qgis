from enum import Enum
from pathlib import Path

from mako.template import Template
from msgspec import UNSET, Struct
from pyramid.response import FileResponse, Response

from nextgisweb.env import gettext
from nextgisweb.lib.json import loads as json_loads

from nextgisweb.core.exception import ValidationError
from nextgisweb.feature_layer import IAggregatableFeatureQuery, IFeatureLayer
from nextgisweb.feature_layer.aggregation import MinMaxSpec, UniqueValuesSpec
from nextgisweb.file_upload.api import FileUploadObject
from nextgisweb.file_upload.model import FileUpload
from nextgisweb.resource import DataScope, ResourceFactory, ResourceScope, resource_factory

import qgis_headless as qh
from qgis_headless import Layer, Style

from .model import (
    _GEOM_TYPE_TO_QGIS,
    QgisRasterStyle,
    QgisStyleFormat,
    QgisVectorStyle,
    read_style,
)
from .util import (
    QML_GEOM_TYPE_NAME,
    QML_GEOM_TYPE_SYMBOL_TYPE,
    add_qml_metadata,
    fix_labeling_enabled,
    fix_layer_geometry_type,
    validate_qml_structure,
    validate_symbol_geometry_type,
)

_QML_GEOM_TYPE = {
    Layer.GT_POINT: 0,
    Layer.GT_LINESTRING: 1,
    Layer.GT_POLYGON: 2,
    Layer.GT_MULTIPOINT: 0,
    Layer.GT_MULTILINESTRING: 1,
    Layer.GT_MULTIPOLYGON: 2,
    Layer.GT_POINTZ: 0,
    Layer.GT_LINESTRINGZ: 1,
    Layer.GT_POLYGONZ: 2,
    Layer.GT_MULTIPOINTZ: 0,
    Layer.GT_MULTILINESTRINGZ: 1,
    Layer.GT_MULTIPOLYGONZ: 2,
}


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


_QML_PROMPT_TEMPLATE = Template(
    filename=str(Path(__file__).parent / "template" / "qml_generate_prompt.mako")
)


def _qml_system_prompt(version):
    return _QML_PROMPT_TEMPLATE.render(version=version)


_QML_TOOL = {
    "type": "function",
    "function": {
        "name": "set_qml",
        "description": "Set the QML style for the layer. You MUST provide the complete QML XML in the 'qml' parameter.",
        "parameters": {
            "type": "object",
            "properties": {
                "qml": {
                    "type": "string",
                    "description": "Complete QML XML string - the entire QML document",
                }
            },
            "required": ["qml"],
        },
    },
}


class StyleGenerateBody(Struct, kw_only=True):
    prompt: str


def _get_field_samples(resource, limit=20):
    """Get sample data for fields to help LLM understand the data"""
    feature_query = resource.feature_query()
    if not IAggregatableFeatureQuery.providedBy(feature_query):
        return ""

    specs = []
    field_map = []
    for f in resource.fields:
        if f.datatype == "STRING":
            specs.append(
                (len(specs), "unique_values", UniqueValuesSpec(field=f.keyname, limit=limit))
            )
            field_map.append((f, "unique_values"))
        elif f.datatype in ("INTEGER", "BIGINT"):
            specs.append((len(specs), "min_max", MinMaxSpec(field=f.keyname)))
            field_map.append((f, "min_max"))

    if not specs:
        return ""

    try:
        results = feature_query.aggregate(specs)
    except Exception:
        return ""

    lines = []
    for idx, (f, agg_type) in enumerate(field_map):
        if idx < len(results):
            result = results[idx]
            if agg_type == "unique_values" and hasattr(result, "buckets"):
                values = [str(b.key) for b in result.buckets[:limit] if b.key is not None]
                if values:
                    lines.append(f"- {f.keyname}: {', '.join(values[:10])}")
                    if len(values) > 10:
                        lines.append(f"  ... and {len(values) - 10} more values")
            elif agg_type == "min_max" and hasattr(result, "min"):
                lines.append(f"- {f.keyname}: range {result.min} to {result.max}")

    return "\n".join(lines) if lines else ""


class StyleGenerateResponse(Struct, kw_only=True):
    file_upload: FileUploadObject


def style_generate(resource, request, *, body: StyleGenerateBody) -> StyleGenerateResponse:
    """Generate QML style from natural language prompt using LLM"""
    request.resource_permission(DataScope.read)

    llm = request.env.llm_core
    if not llm.available:
        from pyramid.httpexceptions import HTTPNotFound

        raise HTTPNotFound()

    qgis_version = qh.get_qgis_version()

    fields_desc = "\n".join(
        f"- {f.keyname} ({f.datatype})"
        + (f" — {f.display_name}" if f.display_name and f.display_name != f.keyname else "")
        for f in resource.fields
    )

    values_desc = _get_field_samples(resource)

    geom_type = _GEOM_TYPE_TO_QGIS[resource.geometry_type]
    qml_geometry_type = _QML_GEOM_TYPE[geom_type]
    geom_name = QML_GEOM_TYPE_NAME[qml_geometry_type]
    symbol_type = QML_GEOM_TYPE_SYMBOL_TYPE[qml_geometry_type]

    user_parts = [
        f"Layer resource ID: {resource.id}",
        f"Layer geometry type: {geom_name}. You MUST use a '{symbol_type}' symbol "
        f'(symbol type="{symbol_type}", layer class="Simple{symbol_type.capitalize()}") '
        "— no other symbol type is valid for this layer.",
        "Layer fields:",
        fields_desc,
    ]
    if values_desc:
        user_parts.extend(["", "Sample values:", values_desc])
    user_parts.extend(["", body.prompt])

    client = llm.make_client()
    response = client.chat.completions.create(
        model=llm.effective_model,
        max_tokens=40000,
        messages=[
            {
                "role": "system",
                "content": _qml_system_prompt(qgis_version),
            },
            {
                "role": "user",
                "content": "\n".join(user_parts),
            },
        ],
        tools=[_QML_TOOL],
        tool_choice={"type": "function", "function": {"name": "set_qml"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    args = json_loads(tool_call.function.arguments)
    qml = args["qml"]

    validate_qml_structure(qml)
    validate_symbol_geometry_type(qml, qml_geometry_type)
    qml = fix_layer_geometry_type(qml, qml_geometry_type)
    qml = fix_labeling_enabled(qml)
    qml = add_qml_metadata(qml, resource.id, body.prompt)

    Style.from_string(qml)

    qml_bytes = qml.encode("utf-8")
    fupload = FileUpload(
        size=len(qml_bytes),
        name="style.qml",
        mime_type="application/x-qgis-layer-settings",
    )
    with fupload.data_path.open("wb") as fd:
        fd.write(qml_bytes)
    fupload.write_meta()

    return StyleGenerateResponse(
        file_upload=FileUploadObject(
            id=fupload.id,
            size=fupload.size,
            name=fupload.name or UNSET,
            mime_type=fupload.mime_type or UNSET,
        )
    )


def setup_pyramid(comp, config):
    route = config.add_route(
        "qgis.style_qml",
        "/api/resource/{id:uint}/qml",
        factory=resource_factory,
        overloaded=True,
    )

    route.add_view(style_qml, context=QgisVectorStyle, request_method="GET")
    route.add_view(style_qml, context=QgisRasterStyle, request_method="GET")

    feature_layer_factory = ResourceFactory(context=IFeatureLayer)
    route = config.add_route(
        "qgis.style_generate",
        "/api/resource/{id}/style/generate",
        factory=feature_layer_factory,
    )
    route.add_view(style_generate, request_method="POST")
