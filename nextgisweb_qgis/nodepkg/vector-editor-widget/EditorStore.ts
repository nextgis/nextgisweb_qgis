import { makeAutoObservable, toJS } from "mobx";

import type { GeometryType } from "@nextgisweb/feature-layer/type";
import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";
import type { Composite } from "@nextgisweb/resource/type";
import type {
    EditorStoreOptions as EditorStoreOptionsBase,
    EditorStore as IEditorStore,
} from "@nextgisweb/resource/type/EditorStore";
import type { ResourceRef } from "@nextgisweb/resource/type/api";
import type { Style } from "@nextgisweb/sld/style-editor/type/Style";

import type { Mode, Value } from "../type";

export interface VectorEditorStoreOptions extends EditorStoreOptionsBase {
    geometryType: GeometryType;
}

export class EditorStore implements IEditorStore<Value> {
    readonly identity = "qgis_vector_style";

    mode: Mode = "file";
    svgMarkerLibrary?: number = undefined;
    source?: FileMeta = undefined;
    uploading = false;
    sld: Style | null = null;
    copy_from?: ResourceRef = undefined;
    geometryType: GeometryType;

    constructor({ geometryType, composite }: VectorEditorStoreOptions) {
        makeAutoObservable<EditorStore>(this, {
            identity: false,
            geometryType: false,
        });
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
        } else if (this.mode === "copy") {
            result.copy_from = this.copy_from;
        }
        return toJS(result);
    }
}
