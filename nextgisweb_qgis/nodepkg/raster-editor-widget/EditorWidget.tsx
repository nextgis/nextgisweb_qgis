import { observer } from "mobx-react-lite";

import { FileUploader } from "@nextgisweb/file-upload/file-uploader";

import type {
    EditorWidgetProps,
    EditorWidgetComponent,
} from "@nextgisweb/resource/type";
import type { EditorStore } from "./EditorStore";

import i18n from "@nextgisweb/pyramid/i18n";

import "./EditorWidget.less";

const mUploadText = i18n.gettext("Select QML file");

export const EditorWidget: EditorWidgetComponent<
    EditorWidgetProps<EditorStore>
> = observer(({ store }: EditorWidgetProps<EditorStore>) => {
    return (
        <div className="ngw-qgis-raster-editor-widget">
            <FileUploader
                accept=".qml"
                onChange={(value) => {
                    store.source = value;
                }}
                onUploading={(value) => {
                    store.uploading = value;
                }}
                uploadText={mUploadText}
            />
        </div>
    );
});

EditorWidget.title = i18n.gettext("QGIS style");
EditorWidget.activateOn = { create: true };
EditorWidget.order = -50;
