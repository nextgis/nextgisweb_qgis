import { observer } from "mobx-react-lite";
import { useMemo } from "react";

import { Select } from "@nextgisweb/gui/antd";
import { gettext } from "@nextgisweb/pyramid/i18n";
import type { EditorWidget as IEditorWidget } from "@nextgisweb/resource/type";

import { CopyFromComponent } from "../CopyFromComponent";
import type { Mode } from "../type";

import type { EditorStore } from "./EditorStore";
import { FileModeComponent } from "./component/FileModeComponent";
import { SldModeComponent } from "./component/SldModeComponent";

import "./EditorWidget.less";

type SelectProps = Parameters<typeof Select>[0];
type Option = NonNullable<SelectProps["options"]>[0] & {
    value: Mode;
};

export const EditorWidget: IEditorWidget<EditorStore> = observer(
    ({ store }) => {
        const { mode } = store;
        const modeOpts = useMemo(() => {
            const result: Option[] = [
                { value: "file", label: gettext("Style from file") },
                { value: "sld", label: gettext("User-defined style") },
                { value: "default", label: gettext("Default style") },
                { value: "copy", label: gettext("Copy from resource") },
            ];
            return result;
        }, []);

        const modeComponent = useMemo(() => {
            switch (mode) {
                case "file":
                    return <FileModeComponent store={store} />;
                case "sld":
                    return <SldModeComponent store={store} />;
                case "copy":
                    return (
                        <CopyFromComponent
                            store={store}
                            cls="qgis_raster_style"
                            pickerOptions={{ initParentId: store.parent_id }}
                        />
                    );
                default:
                    <>Default</>;
            }
        }, [store, mode]);

        return (
            <div className="ngw-qgis-raster-editor-widget">
                <Select
                    className="mode"
                    options={modeOpts}
                    value={store.mode}
                    onChange={store.setMode}
                />
                {modeComponent}
            </div>
        );
    }
);

EditorWidget.displayName = "EditorWidget";
EditorWidget.title = gettext("QGIS style");
EditorWidget.activateOn = { create: true };
EditorWidget.order = -50;
