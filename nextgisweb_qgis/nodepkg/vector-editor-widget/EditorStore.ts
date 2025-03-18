import { action, computed, observable, toJS } from "mobx";

import type { FeaureLayerGeometryType } from "@nextgisweb/feature-layer/type/api";
import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";
import type {
    QgisVectorStyleCreate,
    QgisVectorStyleRead,
    QgisVectorStyleUpdate,
} from "@nextgisweb/qgis/type/api";
import type {
    EditorStoreOptions as EditorStoreOptionsBase,
    EditorStore as IEditorStore,
} from "@nextgisweb/resource/type";
import type { ResourceRef } from "@nextgisweb/resource/type/api";
import type { Style } from "@nextgisweb/sld/type/api";

import type { Mode } from "../type";

export interface VectorEditorStoreOptions extends EditorStoreOptionsBase {
    geometryType: FeaureLayerGeometryType;
}

export class EditorStore
    implements
        IEditorStore<
            QgisVectorStyleRead,
            QgisVectorStyleCreate,
            QgisVectorStyleCreate
        >
{
    readonly identity = "qgis_vector_style";
    readonly geometryType: FeaureLayerGeometryType;

    @observable.ref accessor mode: Mode = "file";
    @observable.ref accessor svgMarkerLibrary: number | undefined = undefined;
    @observable.ref accessor source: FileMeta | undefined = undefined;
    @observable.ref accessor uploading = false;
    @observable.ref accessor sld: Style | null = null;
    @observable.ref accessor copy_from: ResourceRef | undefined = undefined;

    constructor({ geometryType }: VectorEditorStoreOptions) {
        this.geometryType = geometryType;
    }

    @computed
    get isValid() {
        return !this.uploading;
    }

    @action
    setMode = (val: Mode) => {
        this.mode = val;
    };

    @action
    setSource = (val?: FileMeta) => {
        this.source = val;
    };

    @action
    setUploading = (val: boolean) => {
        this.uploading = val;
    };

    @action
    setSvgMarkerLibrary = (val?: number) => {
        this.svgMarkerLibrary = val;
    };

    @action
    setSld = (val: Style | null) => {
        this.sld = val;
    };

    @action
    setCopyFrom = (val: ResourceRef) => {
        this.copy_from = val;
    };

    @action
    load(value: QgisVectorStyleRead) {
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

    dump(): QgisVectorStyleUpdate | QgisVectorStyleCreate {
        const result: QgisVectorStyleUpdate = {};
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
