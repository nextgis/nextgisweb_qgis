import { makeAutoObservable, toJS } from "mobx";

import type {
    EditorStore as IEditorStore,
    Operations,
    EditorStoreOptions,
} from "@nextgisweb/resource/type/EditorStore";
import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";

interface Value {
    file_upload?: FileMeta;
    svg_marker_library?: { id: number } | null;
}

export class EditorStore implements IEditorStore<Value> {
    readonly identity = "qgis_vector_style";

    svgMarkerLibrary?: number;
    source?: FileMeta;
    uploading = false;

    operation?: Operations;
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

    load(value: Value) {
        const svgMarkerLibrary = value?.svg_marker_library?.id;
        if (svgMarkerLibrary) {
            this.svgMarkerLibrary = svgMarkerLibrary;
        }
    }

    dump() {
        const result: Value = {};
        if (this.source) {
            result.file_upload = this.source;
        }

        result.svg_marker_library = this.svgMarkerLibrary
            ? { id: this.svgMarkerLibrary }
            : null;

        return toJS(result);
    }

    get isValid() {
        return !this.uploading;
    }
}
