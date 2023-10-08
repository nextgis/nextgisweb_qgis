import { observer } from "mobx-react-lite";

import { FileUploader } from "@nextgisweb/file-upload/file-uploader";
import { gettext } from "@nextgisweb/pyramid/i18n";
import type {
    EditorWidgetComponent,
    EditorWidgetProps,
} from "@nextgisweb/resource/type";

import type { EditorStore } from "./EditorStore";

import "./EditorWidget.less";

const msgUploadText = gettext("Select a style");
const msgHelpText = gettext("QML or SLD formats are supported.");

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
                uploadText={msgUploadText}
                helpText={msgHelpText}
            />
        </div>
    );
});

EditorWidget.title = gettext("QGIS style");
EditorWidget.activateOn = { create: true };
EditorWidget.order = -50;
