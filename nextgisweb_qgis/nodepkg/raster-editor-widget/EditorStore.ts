import { makeAutoObservable, toJS } from "mobx";

import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";
import type { Composite } from "@nextgisweb/resource/type/Composite";
import type {
    EditorStoreOptions,
    EditorStore as IEditorStore,
    Operation,
} from "@nextgisweb/resource/type/EditorStore";
import type { ResourceRef } from "@nextgisweb/resource/type/api";
import type { Style } from "@nextgisweb/sld/style-editor/type/Style";

export type Mode = "file" | "sld" | "copy" | "default";

interface Value {
    file_upload?: FileMeta;
    format?: "default" | "sld";
    sld?: Style;
    copy_from?: ResourceRef;
}

export class EditorStore implements IEditorStore<Value> {
    readonly identity = "qgis_raster_style";

    mode: Mode = "file";
    source?: FileMeta = undefined;
    uploading = false;
    sld: Style | null = null;
    copy_from?: ResourceRef = undefined;

    operation?: Operation;
    composite: Composite;

    constructor({ composite, operation }: EditorStoreOptions) {
        makeAutoObservable(this, {
            identity: false,
            operation: false,
            composite: false,
        });
        this.operation = operation;
        this.composite = composite as Composite;
    }

    get isValid() {
        return !this.uploading;
    }

    setMode = (val: Mode) => {
        this.mode = val;
    };

    setSource = (val?: FileMeta) => {
        this.source = val;
    };

    setUploading = (val: boolean) => {
        this.uploading = val;
    };

    setSld = (val: Style | null) => {
        this.sld = val;
    };

    setCopyFrom = (val: ResourceRef) => {
        this.copy_from = val;
    };

    load(value: Value) {
        if (value.sld) {
            this.sld = value.sld;
            this.mode = "sld";
        } else if (value.format === "default") {
            this.mode = "default";
        }
    }

    dump() {
        const result: Value = {};
        if (this.mode === "file") {
            if (this.source) {
                result.file_upload = this.source;
            }
        } else if (this.mode === "sld") {
            if (this.sld) {
                result.sld = this.sld;
                result.format = "sld";
            }
        } else if (this.mode === "default") {
            result.format = "default";
        } else if (this.mode === "copy") {
            result.copy_from = this.copy_from;
        }
        return toJS(result);
    }
}
