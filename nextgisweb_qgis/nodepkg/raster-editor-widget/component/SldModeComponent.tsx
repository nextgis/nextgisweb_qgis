import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";

import { Form, InputNumber, Select, Space } from "@nextgisweb/gui/antd";
import type { InputNumberProps } from "@nextgisweb/gui/antd";
import { route } from "@nextgisweb/pyramid/api";
import { gettext } from "@nextgisweb/pyramid/i18n";
import type {
    EditorWidgetProps,
    ResourceItem,
} from "@nextgisweb/resource/type";

import type { EditorStore } from "../EditorStore";

interface BandOptions {
    label: string;
    value: string;
}

const defInputProps: InputNumberProps = { min: 0, max: 255 };

export const SldModeComponent = observer(
    ({ store }: EditorWidgetProps<EditorStore>) => {
        const [form] = Form.useForm();
        const resourceId = store.composite.parent;

        const [bands, setBands] = useState<BandOptions[]>([]);
        useEffect(() => {
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
                            value: value,
                            label: `${index + 1}: ${value}`,
                        }))
                    );
                }
            }
            getBands();
        }, [resourceId]);

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
            >
                <Form.Item>
                    <Form.Item name="redChannel" label={gettext("Red channel")}>
                        <Select labelInValue options={bands} />
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
                        <Select labelInValue options={bands} />
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
                        <Select labelInValue options={bands} />
                    </Form.Item>
                    <Space>
                        <Form.Item label="Min" name="blueChannelMax">
                            <InputNumber {...defInputProps} />
                        </Form.Item>
                        <Form.Item label="Max" name="blueChannelMin">
                            <InputNumber {...defInputProps} />
                        </Form.Item>
                    </Space>
                </Form.Item>
            </Form>
        );
    }
);
