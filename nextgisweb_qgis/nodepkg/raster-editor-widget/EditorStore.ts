import { makeAutoObservable, toJS } from "mobx";

import type {
    EditorStore as IEditorStore,
    Operations,
    EditorStoreOptions,
} from "@nextgisweb/resource/type/EditorStore";

export class EditorStore implements IEditorStore {
    readonly identity = "qgis_raster_style";

    source = null;
    uploading = false;

    operation: Operations;
    composite: unknown;

    constructor({ composite, operation }: EditorStoreOptions) {
        makeAutoObservable(this, {
            identity: false,
            operation: false,
            composite: false,
        });
        this.operation = operation;
        this.composite = composite;
    }

    load() {
        // ignore
    }

    dump() {
        const result = {} as { file_upload: Record<string, any> };
        if (this.source) {
            result.file_upload = this.source;
        }
        return toJS(result);
    }

    get isValid() {
        return (
            !this.uploading && (this.operation === "update" || !!this.source)
        );
    }
}
