import { makeAutoObservable, toJS } from "mobx";

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

    mode: Mode = "file";
    source?: FileMeta = undefined;
    uploading = false;
    sld: Style | null = null;
    copy_from?: ResourceRef = undefined;

    parent_id: number;
    band_count: number;
    dtype: Dtype;

    constructor({ parent_id, band_count, dtype }: RasterEditorStoreOptions) {
        makeAutoObservable(this, {
            identity: false,
            dtype: false,
            parent_id: false,
            band_count: false,
        });
        this.parent_id = parent_id;
        this.band_count = band_count;
        this.dtype = dtype;
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
