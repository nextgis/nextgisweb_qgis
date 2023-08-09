import { observer } from "mobx-react-lite";

import { FileUploader } from "@nextgisweb/file-upload/file-uploader";

import type {
    EditorWidgetProps,
    EditorWidgetComponent,
} from "@nextgisweb/resource/type";
import type { EditorStore } from "./EditorStore";

import { gettext } from "@nextgisweb/pyramid/i18n";

import "./EditorWidget.less";

const mUploadText = gettext("Select a style");
const mHelpText = gettext("QML or SLD formats are supported.")

export const EditorWidget: EditorWidgetComponent<
    EditorWidgetProps<EditorStore>
> = observer(({ store }: EditorWidgetProps<EditorStore>) => {
    return (
        <div className="ngw-qgis-raster-editor-widget">
            <FileUploader
                accept=".qml,.sld"
                onChange={(value) => {
                    store.source = value;
                }}
                onUploading={(value) => {
                    store.uploading = value;
                }}
                uploadText={mUploadText}
                helpText={mHelpText}
            />
        </div>
    );
});

EditorWidget.title = gettext("QGIS style");
EditorWidget.activateOn = { create: true };
EditorWidget.order = -50;
