import { makeAutoObservable, toJS } from "mobx";

import type { GeometryType } from "@nextgisweb/feature-layer/type";
import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";
import type {
    EditorStoreOptions as EditorStoreOptionsBase,
    EditorStore as IEditorStore,
    Operations,
} from "@nextgisweb/resource/type/EditorStore";
import type { Style } from "@nextgisweb/sld/style-editor/type/Style";

interface Value {
    file_upload?: FileMeta;
    svg_marker_library?: { id: number } | null;
    format?: "default" | "sld";
    sld?: Style;
}

export type Mode = "file" | "sld" | "default";

interface Composite {
    parent: number;
}

interface EditorStoreOptions extends EditorStoreOptionsBase {
    geometryType: GeometryType;
}

export class EditorStore implements IEditorStore<Value> {
    readonly identity = "qgis_vector_style";

    mode: Mode = "file";
    svgMarkerLibrary?: number = undefined;
    source?: FileMeta = undefined;
    uploading = false;
    sld: Style | null = null;

    operation?: Operations;
    composite: Composite;
    geometryType: GeometryType;

    constructor({ composite, operation, geometryType }: EditorStoreOptions) {
        makeAutoObservable<EditorStore>(this, {
            identity: false,
            operation: false,
            composite: false,
        });
        this.operation = operation;
        this.composite = composite as Composite;
        this.geometryType = geometryType;
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

    setSvgMarkerLibrary = (val?: number) => {
        this.svgMarkerLibrary = val;
    };

    setSld = (val: Style | null) => {
        this.sld = val;
    };

    load(value: Value) {
        if (value.sld) {
            this.sld = value.sld;
            this.mode = "sld";
        } else if (value.format === "default") {
            this.mode = "default";
        }
        const svgMarkerLibrary = value?.svg_marker_library?.id;
        if (svgMarkerLibrary) {
            this.svgMarkerLibrary = svgMarkerLibrary;
        }
    }

    dump() {
        const result: Value = {};
        if (this.mode === "file") {
            if (this.source) {
                result.file_upload = this.source;
            }

            result.svg_marker_library = this.svgMarkerLibrary
                ? { id: this.svgMarkerLibrary }
                : null;
        } else if (this.mode === "sld") {
            if (this.sld) {
                result.sld = this.sld;
                result.format = "sld";
            }
        } else if (this.mode === "default") {
            result.format = "default";
        }

        return toJS(result);
    }
}
