import { observer } from "mobx-react-lite";

import { FileUploader } from "@nextgisweb/file-upload/file-uploader";

import i18n from "@nextgisweb/pyramid/i18n";
import "./EditorWidget.less";

// prettier-ignore
const uploaderMessages = {
    uploadText: i18n.gettext("Select a QML file"),
}

export const EditorWidget = observer(({ store }) => {
    return (
        <div className="ngw-qgis-raster-editor-widget">
            <FileUploader
                accept=".qml"
                onChange={(value) => {
                    store.source = value;
                }}
                onUploading={(value) => {
                    store.uploding = value;
                }}
                {...uploaderMessages}
            />
        </div>
    );
});

EditorWidget.title = i18n.gettext("QGIS style");
EditorWidget.activateOn = { create: true };
EditorWidget.order = -50;
