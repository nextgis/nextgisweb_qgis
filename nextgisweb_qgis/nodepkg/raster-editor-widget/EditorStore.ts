import { isEqual } from "lodash-es";
import { action, computed, observable } from "mobx";

import type { FileMeta } from "@nextgisweb/file-upload/file-uploader";
import type {
    QgisRasterStyleCreate,
    QgisRasterStyleRead,
    QgisRasterStyleUpdate,
} from "@nextgisweb/qgis/type/api";
import type {
    EditorStoreOptions,
    EditorStore as IEditorStore,
} from "@nextgisweb/resource/type";
import type { ResourceRef } from "@nextgisweb/resource/type/api";
import type { Style } from "@nextgisweb/sld/type/api";

export type Mode = "file" | "sld" | "copy" | "default";

type Dtype = "Int16" | "Int32" | "UInt16" | "UInt32" | "Byte";

export interface RasterEditorStoreOptions extends EditorStoreOptions {
    dtype: Dtype;
    parent_id: number;
    band_count: number;
}

export class EditorStore implements IEditorStore<
    QgisRasterStyleRead,
    QgisRasterStyleCreate,
    QgisRasterStyleUpdate
> {
    readonly identity = "qgis_raster_style";

    @observable.ref accessor mode: Mode = "file";
    @observable.ref accessor source: FileMeta | null = null;
    @observable.ref accessor sld: Style | null = null;
    @observable.ref accessor copyFrom: ResourceRef | null = null;

    @observable.ref accessor dirty = false;
    @observable.ref accessor uploading = false;

    readonly parent_id: number;
    readonly band_count: number;
    readonly dtype: Dtype;

    constructor({ parent_id, band_count, dtype }: RasterEditorStoreOptions) {
        this.parent_id = parent_id;
        this.band_count = band_count;
        this.dtype = dtype;
    }

    @action
    load(value: QgisRasterStyleRead) {
        if (value.sld) {
            this.sld = value.sld ?? null;
            this.mode = "sld";
        } else if (value.format === "default") {
            this.mode = "default";
        }
    }

    dump() {
        if (!this.dirty) return undefined;

        const result: QgisRasterStyleUpdate = {};
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
            result.copy_from = this.copyFrom ?? undefined;
        }
        return result;
    }

    @computed
    get isValid() {
        return !this.uploading;
    }

    @action.bound
    setMode(value: Mode) {
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
    setUploading(val: boolean) {
        this.uploading = val;
    }
}
