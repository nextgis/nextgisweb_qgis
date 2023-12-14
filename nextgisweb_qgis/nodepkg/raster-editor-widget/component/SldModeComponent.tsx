import { observer } from "mobx-react-lite";
import { useCallback, useLayoutEffect, useMemo, useState } from "react";

import { Form, InputNumber, Select, Space } from "@nextgisweb/gui/antd";
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
                            label: `${index + 1}: ${value}`,
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
            >
                <Form.Item>
                    <Form.Item name="redChannel" label={gettext("Red channel")}>
                        <Select options={bands} />
                    </Form.Item>
                    <Space>
                        <Form.Item label="Min" name="redChannelMin">
                            <InputNumber {...defInputProps} />
                        </Form.Item>
                        <Form.Item label="Max" name="redChannelMax">
                            <InputNumber {...defInputProps} />
                        </Form.Item>
                    </Space>
                </Form.Item>
                <Form.Item>
                    <Form.Item
                        name="greenChannel"
                        label={gettext("Green channel")}
                    >
                        <Select options={bands} />
                    </Form.Item>
                    <Space>
                        <Form.Item label="Min" name="greenChannelMin">
                            <InputNumber {...defInputProps} />
                        </Form.Item>
                        <Form.Item label="Max" name="greenChannelMax">
                            <InputNumber {...defInputProps} />
                        </Form.Item>
                    </Space>
                </Form.Item>
                <Form.Item>
                    <Form.Item
                        name="blueChannel"
                        label={gettext("Blue channel")}
                    >
                        <Select options={bands} />
                    </Form.Item>
                    <Space>
                        <Form.Item label="Min" name="blueChannelMin">
                            <InputNumber {...defInputProps} />
                        </Form.Item>
                        <Form.Item label="Max" name="blueChannelMax">
                            <InputNumber {...defInputProps} />
                        </Form.Item>
                    </Space>
                </Form.Item>
            </Form>
        );
    }
);
