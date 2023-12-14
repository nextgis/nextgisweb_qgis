import { observer } from "mobx-react-lite";
import { useCallback, useLayoutEffect, useMemo, useState } from "react";

import { Form, InputNumber, Select } from "@nextgisweb/gui/antd";
import type { InputNumberProps } from "@nextgisweb/gui/antd";
import { route } from "@nextgisweb/pyramid/api";
import { gettext } from "@nextgisweb/pyramid/i18n";
import type { ResourceItem } from "@nextgisweb/resource/type";
import type { EditorWidgetProps } from "@nextgisweb/resource/type";
import type {
    RasterSymbolizer,
    Symbolizer,
} from "@nextgisweb/sld/style-editor/type/Style";

import type { EditorStore } from "../EditorStore";
import { getSymbolizerValues } from "../util/getSymbolizerValues";

import "./SldModeComponent.less";

interface BandOptions {
    label: string;
    value: number;
}

const defInputProps: InputNumberProps = { min: 0, max: 255 };

export const SldModeComponent = observer(
    ({ store }: EditorWidgetProps<EditorStore>) => {
        const { sld } = store;

        const symbolizer_ = useMemo(
            () => sld?.rules[0]?.symbolizers[0],
            [sld]
        ) as RasterSymbolizer;

        const [form] = Form.useForm();
        const resourceId = store.composite.parent;

        const initialValues = getSymbolizerValues(symbolizer_);

        const [bands, setBands] = useState<BandOptions[]>([]);
        useLayoutEffect(() => {
            async function getBands() {
                const rasterRes = await route("resource.item", {
                    id: resourceId,
                }).get<ResourceItem>({
                    cache: true,
                });
                if (rasterRes.raster_layer) {
                    const bands_ = rasterRes.raster_layer.color_interpretation;
                    setBands(
                        bands_.map((value, index) => ({
                            key: index,
                            value: index,
                            label:
                                gettext("Band {}").replace(
                                    "{}",
                                    `${index + 1}`
                                ) + (value ? ` (${value})` : ""),
                        }))
                    );
                }
            }
            getBands();
        }, [resourceId]);

        const onChange = useCallback(
            (valueChange, allValues) => {
                const symbolizer = {
                    type: "raster",
                    channels: {
                        red: {
                            source_channel: allValues.redChannel
                                ? allValues.redChannel
                                : 0,
                            contrast_enhancement: {
                                normalize: {
                                    algorithm: "stretch",
                                    min_value: allValues.redChannelMin,
                                    max_value: allValues.redChannelMax,
                                },
                            },
                        },
                        green: {
                            source_channel: allValues.greenChannel
                                ? allValues.greenChannel
                                : 0,
                            contrast_enhancement: {
                                normalize: {
                                    algorithm: "stretch",
                                    min_value: allValues.greenChannelMin,
                                    max_value: allValues.greenChannelMax,
                                },
                            },
                        },
                        blue: {
                            source_channel: allValues.blueChannel
                                ? allValues.blueChannel
                                : 0,
                            contrast_enhancement: {
                                normalize: {
                                    algorithm: "stretch",
                                    min_value: allValues.blueChannelMin,
                                    max_value: allValues.blueChannelMax,
                                },
                            },
                        },
                    },
                } as Symbolizer;
                store.setSld({ rules: [{ symbolizers: [symbolizer] }] });
            },

            [store]
        );

        return (
            <Form
                form={form}
                initialValues={initialValues}
                onValuesChange={onChange}
                className="ngw-qgis-raster-editor-widget-sld"
            >
                <label>{gettext("Red channel")}</label>
                <Form.Item noStyle name="redChannel">
                    <Select options={bands} />
                </Form.Item>
                <label className="min">{gettext("Min")}</label>
                <Form.Item noStyle name="redChannelMin">
                    <InputNumber {...defInputProps} />
                </Form.Item>
                <label className="max">{gettext("Max")}</label>
                <Form.Item noStyle name="redChannelMax">
                    <InputNumber {...defInputProps} />
                </Form.Item>

                <label>{gettext("Green channel")}</label>
                <Form.Item noStyle name="greenChannel">
                    <Select options={bands} />
                </Form.Item>
                <label className="min">{gettext("Min")}</label>
                <Form.Item noStyle name="greenChannelMin">
                    <InputNumber {...defInputProps} />
                </Form.Item>
                <label className="max">{gettext("Max")}</label>
                <Form.Item noStyle name="greenChannelMax">
                    <InputNumber {...defInputProps} />
                </Form.Item>

                <label>{gettext("Blue channel")}</label>
                <Form.Item noStyle name="blueChannel">
                    <Select options={bands} />
                </Form.Item>
                <label className="min">{gettext("Min")}</label>
                <Form.Item noStyle name="blueChannelMin">
                    <InputNumber {...defInputProps} />
                </Form.Item>
                <label className="max">{gettext("Max")}</label>
                <Form.Item noStyle name="blueChannelMax">
                    <InputNumber {...defInputProps} />
                </Form.Item>
            </Form>
        );
    }
);
