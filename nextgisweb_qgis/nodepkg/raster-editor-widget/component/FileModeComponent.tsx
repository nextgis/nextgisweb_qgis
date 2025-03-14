import { observer } from "mobx-react-lite";

import { FileUploader } from "@nextgisweb/file-upload/file-uploader";
import { gettext } from "@nextgisweb/pyramid/i18n";
import type { EditorWidget } from "@nextgisweb/resource/type";

import type { EditorStore } from "../EditorStore";

const msgUploadText = gettext("Select a style");
const msgHelpText = gettext("QML or SLD formats are supported.");

export const FileModeComponent: EditorWidget<EditorStore> = observer(
    ({ store }) => {
        return (
            <>
                <FileUploader
                    accept=".qml,.sld"
                    onChange={(value) => {
                        if (Array.isArray(value)) throw "unreachable";
                        store.setSource(value);
                    }}
                    onUploading={(value) => {
                        store.setUploading(value);
                    }}
                    uploadText={msgUploadText}
                    helpText={msgHelpText}
                />
            </>
        );
    }
);

FileModeComponent.displayName = "FileModeComponent";
