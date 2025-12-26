import { isEqual } from "lodash-es";
import { action, computed, observable } from "mobx";

import type { FeatureLayerGeometryType } from "@nextgisweb/feature-layer/type/api";
import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";
import type {
    QgisVectorStyleCreate,
    QgisVectorStyleRead,
    QgisVectorStyleUpdate,
} from "@nextgisweb/qgis/type/api";
import type {
    EditorStoreOptions,
    EditorStore as IEditorStore,
} from "@nextgisweb/resource/type";
import type { ResourceRef } from "@nextgisweb/resource/type/api";
import type { Style } from "@nextgisweb/sld/type/api";

export type Mode = "file" | "sld" | "copy" | "default";

export interface VectorEditorStoreOptions extends EditorStoreOptions {
    geometryType: FeatureLayerGeometryType;
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
    readonly geometryType: FeatureLayerGeometryType;

    @observable.ref accessor mode: Mode = "file";
    @observable.ref accessor source: FileMeta | null = null;
    @observable.ref accessor sld: Style | null = null;
    @observable.ref accessor svgMarkerLibrary: number | null = null;
    @observable.ref accessor copyFrom: ResourceRef | null = null;

    @observable.ref accessor dirty = false;
    @observable.ref accessor uploading = false;

    constructor({ geometryType }: VectorEditorStoreOptions) {
        this.geometryType = geometryType;
    }

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

        this.dirty = false;
    }

    dump() {
        if (!this.dirty) return undefined;

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
            result.copy_from = this.copyFrom ?? undefined;
        }
        return result;
    }

    @computed
    get isValid() {
        return !this.uploading;
    }

    @action.bound
    setMode(value: this["mode"]) {
        this.mode = value;
        this.dirty = true;
    }

    @action.bound
    setSource(value: this["source"] | undefined) {
        value = value ?? null;
        if (this.source === (value ?? null)) return;
        this.source = value;
        this.dirty = true;
    }

    @action.bound
    setSvgMarkerLibrary(value: this["svgMarkerLibrary"] | undefined) {
        value = value ?? null;
        this.svgMarkerLibrary = value;
        this.dirty = true;
    }

    @action.bound
    setSld(value: this["sld"]) {
        if (isEqual(this.sld, value)) return;
        this.sld = value;
        this.dirty = true;
    }

    @action.bound
    setCopyFrom(value: this["copyFrom"]) {
        this.copyFrom = value;
        this.dirty = true;
    }

    @action.bound
    setUploading(value: this["uploading"]) {
        this.uploading = value;
    }
}
