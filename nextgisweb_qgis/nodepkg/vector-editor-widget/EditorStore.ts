import { makeAutoObservable, toJS, runInAction } from "mobx";

import { route } from "@nextgisweb/pyramid/api";
import { AbortControllerHelper } from "@nextgisweb/pyramid/util/abort";

import type {
    EditorStore as IEditorStore,
    Operations,
    EditorStoreOptions,
} from "@nextgisweb/resource/type/EditorStore";
import type { GeometryType } from "@nextgisweb/feature-layer/type";
import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";
import type { Style } from "@nextgisweb/sld/style-editor/type/Style";
import type { ResourceItem } from "@nextgisweb/resource/type/Resource";

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

export class EditorStore implements IEditorStore<Value> {
    readonly identity = "qgis_vector_style";

    svgMarkerLibrary?: number = undefined;
    source?: FileMeta = undefined;
    uploading = false;

    ready = false;
    geometryType: GeometryType | null = null;

    sld: Style | null = null;

    mode: Mode = "file";

    operation?: Operations;
    composite: Composite;

    private _resourceAbort = new AbortControllerHelper();

    constructor({ composite, operation }: EditorStoreOptions) {
        makeAutoObservable<EditorStore, "_resourceAbort">(this, {
            identity: false,
            operation: false,
            composite: false,
            _resourceAbort: false,
        });
        this.operation = operation;
        this.composite = composite as Composite;
        this._init();
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

    private _init() {
        const parentResourceId = this.composite.parent;
        if (parentResourceId !== undefined) {
            route("resource.item", { id: parentResourceId })
                .get<ResourceItem>({
                    cache: true,
                    signal: this._resourceAbort.makeSignal(),
                })
                .then((res) => {
                    const vectorLayer = res.vector_layer;
                    if (vectorLayer) {
                        runInAction(() => {
                            this.geometryType = vectorLayer.geometry_type;
                        });
                    }
                })
                .finally(() => {
                    runInAction(() => {
                        this.ready = true;
                    });
                });
        }
    }
}
