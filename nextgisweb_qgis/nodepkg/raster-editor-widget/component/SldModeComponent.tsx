import { observer } from "mobx-react-lite";
import { useCallback, useLayoutEffect, useMemo, useState } from "react";

import { Form, InputNumber, Select, Space } from "@nextgisweb/gui/antd";
import { route } from "@nextgisweb/pyramid/api";
import { gettext } from "@nextgisweb/pyramid/i18n";
import type { EditorWidgetProps } from "@nextgisweb/resource/type";
import type { Symbolizer } from "@nextgisweb/sld/style-editor/type/Style";

import type { EditorStore } from "../EditorStore";

export const SldModeComponent = observer(
    ({ store }: EditorWidgetProps<EditorStore>) => {
        const { sld } = store;

        const [form] = Form.useForm();
        const resourceId = store.composite.parent;

        const [bands, setBands] = useState(null);
        useLayoutEffect(() => {
            async function getBands() {
                const rasterInfo = await route("resource.item", {
                    id: resourceId,
                }).get<any>({
                    cache: true,
                });
                const bands_ = rasterInfo.raster_layer.color_interpretation;
                setBands(
                    bands_.map((value, index) => ({
                        value: value,
                        label: `${index + 1}: ${value}`,
                    }))
                );
            }
            getBands();
        }, []);
        // const onChange = useCallback(
        //     (val: Symbolizer) =>
        //         store.setSld({ rules: [{ symbolizers: [val] }] }),

        //     [store]
        // );

        const onChange = (event) => {
            form.getFieldsValue();
            console.log("changed");
        };
        const symbolizer = useMemo(() => sld?.rules[0]?.symbolizers[0], [sld]);
        return (
            <Form
                form={form}
                initialValues={{
                    redChannelMin: 0,
                    redChannelMax: 255,
                    greenChannelMin: 0,
                    greenChannelMax: 255,
                    blueChannelMin: 0,
                    blueChannelMax: 255,
                }}
                onChange={onChange}
            >
                <Form.Item>
                    <Form.Item name="redChannel" label={gettext("Red channel")}>
                        <Select
                            labelInValue
                            options={bands}
                            onChange={onChange}
                        />
                    </Form.Item>
                    <Space>
                        <Form.Item label="Min" name="redChannelMin">
                            <InputNumber min={0} max={255} />
                        </Form.Item>
                        <Form.Item label="Max" name="redChannelMax">
                            <InputNumber min={0} max={255} />
                        </Form.Item>
                    </Space>
                </Form.Item>
                <Form.Item>
                    <Form.Item
                        name="greenChannel"
                        label={gettext("Green channel")}
                    >
                        <Select
                            labelInValue
                            options={bands}
                            onChange={onChange}
                        />
                    </Form.Item>
                    <Space>
                        <Form.Item label="Min" name="greenChannelMin">
                            <InputNumber min={0} max={255} />
                        </Form.Item>
                        <Form.Item label="Max" name="greenChannelMax">
                            <InputNumber min={0} max={255} />
                        </Form.Item>
                    </Space>
                </Form.Item>
                <Form.Item>
                    <Form.Item
                        name="blueChannel"
                        label={gettext("Blue channel")}
                    >
                        <Select
                            labelInValue
                            options={bands}
                            onChange={onChange}
                        />
                    </Form.Item>
                    <Space>
                        <Form.Item label="Min" name="blueChannelMax">
                            <InputNumber min={0} max={255} />
                        </Form.Item>
                        <Form.Item label="Max" name="blueChannelMin">
                            <InputNumber min={0} max={255} />
                        </Form.Item>
                    </Space>
                </Form.Item>
            </Form>
        );
    }
);
