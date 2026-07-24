from enum import Enum

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
from qgis_headless import Style

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


_QML_SCHEMA = """
You are an expert QGIS cartographer and QML generator.

Generate a complete, valid QML style compatible with QGIS {version}.

Layer fields:
{fields_desc}

General rules:
- You MUST call the set_qml function.
- The `qml` parameter MUST contain ONLY the XML document, beginning with `<?xml`.
- Do not output markdown, explanations, comments, or any text outside the XML.
- The generated QML must load successfully in QGIS {version}.

Renderer selection:
- Use a Single Symbol renderer when one symbol is sufficient.
- Use a Categorized renderer for discrete attribute values.
- Use a Graduated renderer for numeric ranges.
- Use a Rule-Based renderer when styling depends on multiple rules, feature hierarchy, rendering order, or multiple attributes.

QML generation:
- Generate the SMALLEST valid QML.
- Include ONLY XML elements required to reproduce the requested appearance.
- Omit properties that use QGIS default values.
- Do not duplicate default <Option> or <prop> entries.
- Do not invent unsupported XML elements or properties.
- Every referenced symbol must exist exactly once.
- Keep symbol definitions compact.
- Reuse symbols whenever practical.
- Produce syntactically valid XML with properly closed elements.
- No indentation.
- No line breaks except inside XML declaration if required.
- No extra whitespace between elements.

Cartographic principles:
- Prioritize readability.
- Build a clear visual hierarchy.
- Use symbol size or line width as the primary indicator of importance.
- Use color as a secondary visual variable.
- Minimize the number of colors.
- Similar feature classes should share similar styling.
- More important features should visually dominate.
- Less important features should recede.
- Avoid decorative styling.
- Avoid highly saturated colors unless explicitly requested.
- Prefer established cartographic conventions over arbitrary styling.

Road styling:
- Prefer a Rule-Based renderer.
- Draw roads from least important to most important.
- Use line width as the primary indicator of hierarchy.
- Keep related road classes visually similar.
- Major roads may use a casing.
- Construction and proposed roads should use dashed lines.
- Prefer a restrained palette similar to OpenStreetMap Carto rather than assigning unique colors to every road class.

Quality:
- Produce deterministic output.
- Do not include XML comments.
- Do not include redundant metadata.
- Do not include unused symbols.
- Do not include properties that do not affect rendering.

"""

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

    prompt_content = body.prompt
    if values_desc:
        prompt_content = f"{body.prompt}\n\nSample values:\n{values_desc}"

    client = llm.make_client()
    response = client.chat.completions.create(
        model=llm.effective_model,
        max_tokens=40000,
        messages=[
            {
                "role": "system",
                "content": _QML_SCHEMA.format(version=qgis_version, fields_desc=fields_desc),
            },
            {
                "role": "user",
                "content": prompt_content,
            },
        ],
        tools=[_QML_TOOL],
        tool_choice={"type": "function", "function": {"name": "set_qml"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    args = json_loads(tool_call.function.arguments)
    qml = args["qml"]

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
