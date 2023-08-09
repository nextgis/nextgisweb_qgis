import { observer } from "mobx-react-lite";

import { FileUploader } from "@nextgisweb/file-upload/file-uploader";
import { ResourceSelect } from "@nextgisweb/resource/component/resource-select";

import { gettext } from "@nextgisweb/pyramid/i18n";

import type {
    EditorWidgetComponent,
    EditorWidgetProps,
} from "@nextgisweb/resource/type";
import type { EditorStore } from "./EditorStore";

import "./EditorWidget.less";

const mUploadText = gettext("Select a style");
const mHelpText = gettext("QML or SLD formats are supported.")
const mSvgMarkerLibrary = gettext("SVG marker library");

export const EditorWidget: EditorWidgetComponent<
    EditorWidgetProps<EditorStore>
> = observer(({ store }: EditorWidgetProps<EditorStore>) => {
    return (
        <div className="ngw-qgis-vector-editor-widget">
            <FileUploader
                accept=".qml,.sld"
                onChange={(value) => {
                    if (Array.isArray(value)) throw "unreachable";
                    store.source = value;
                }}
                onUploading={(value) => {
                    store.uploading = value;
                }}
                uploadText={mUploadText}
                helpText={mHelpText}
            />
            <label>{mSvgMarkerLibrary}</label>
            <ResourceSelect
                value={store.svgMarkerLibrary}
                onChange={(value) => {
                    if (Array.isArray(value)) throw "unreachable";
                    store.svgMarkerLibrary = value;
                }}
                pickerOptions={{
                    traverseClasses: ["resource_group"],
                    requireClass: "svg_marker_library",
                    hideUnavailable: true,
                }}
                allowClear
            />
        </div>
    );
});

EditorWidget.title = gettext("QGIS style");
EditorWidget.activateOn = { create: true };
EditorWidget.order = -50;
