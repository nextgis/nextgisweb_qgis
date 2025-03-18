import { action, computed, observable, toJS } from "mobx";

import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";
import type {
    QgisRasterStyleCreate,
    QgisRasterStyleRead,
    QgisRasterStyleUpdate,
} from "@nextgisweb/qgis/type/api";
import type {
    EditorStoreOptions as EditorStoreOptionsBase,
    EditorStore as IEditorStore,
} from "@nextgisweb/resource/type";
import type { ResourceRef } from "@nextgisweb/resource/type/api";
import type { Style } from "@nextgisweb/sld/type/api";

import type { Mode } from "../type";

type Dtype = "Int16" | "Int32" | "UInt16" | "UInt32" | "Byte";
export interface RasterEditorStoreOptions
    extends Omit<EditorStoreOptionsBase, "composite"> {
    dtype: Dtype;
    parent_id: number;
    band_count: number;
}

export class EditorStore
    implements
        IEditorStore<
            QgisRasterStyleRead,
            QgisRasterStyleCreate,
            QgisRasterStyleUpdate
        >
{
    readonly identity = "qgis_raster_style";

    @observable.ref accessor mode: Mode = "file";
    @observable.ref accessor source: FileMeta | undefined = undefined;
    @observable.ref accessor uploading = false;
    @observable.ref accessor sld: Style | null = null;
    @observable.ref accessor copy_from: ResourceRef | undefined = undefined;

    readonly parent_id: number;
    readonly band_count: number;
    readonly dtype: Dtype;

    constructor({ parent_id, band_count, dtype }: RasterEditorStoreOptions) {
        this.parent_id = parent_id;
        this.band_count = band_count;
        this.dtype = dtype;
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
    setSld = (val: Style | null) => {
        this.sld = val;
    };

    @action
    setCopyFrom = (val: ResourceRef) => {
        this.copy_from = val;
    };

    @action
    load(value: QgisRasterStyleRead) {
        if (value.sld) {
            this.sld = value.sld ?? null;
            this.mode = "sld";
        } else if (value.format === "default") {
            this.mode = "default";
        }
    }

    dump(): QgisRasterStyleCreate | QgisRasterStyleUpdate {
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
            result.copy_from = this.copy_from;
        }
        return toJS(result);
    }
}
