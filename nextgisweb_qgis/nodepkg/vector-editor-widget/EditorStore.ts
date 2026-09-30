import { isEqual } from "lodash-es";
import { action, actionBound, computed, observableRef } from "mobx";

import type { FeatureLayerGeometryType } from "@nextgisweb/feature-layer/type/api";
import type { FileMeta } from "@nextgisweb/file-upload/file-uploader/type";
import type {
  QgisVectorStyleCreate,
  QgisVectorStyleRead,
  QgisVectorStyleUpdate,
} from "@nextgisweb/qgis/type/api";
import type { CompositeStore } from "@nextgisweb/resource/composite";
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

export class EditorStore implements IEditorStore<
  QgisVectorStyleRead,
  QgisVectorStyleCreate,
  QgisVectorStyleCreate
> {
  readonly identity = "qgis_vector_style";
  readonly geometryType: FeatureLayerGeometryType;
  readonly composite?: CompositeStore;

  @observableRef accessor mode: Mode = "file";
  @observableRef accessor source: FileMeta | null = null;
  @observableRef accessor sld: Style | null = null;
  @observableRef accessor svgMarkerLibrary: number | null = null;
  @observableRef accessor copyFrom: ResourceRef | null = null;

  @observableRef accessor dirty = false;
  @observableRef accessor uploading = false;

  constructor({ geometryType, composite }: VectorEditorStoreOptions) {
    this.composite = composite;
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

  @actionBound
  setMode(value: this["mode"]) {
    this.mode = value;
    this.dirty = true;
  }

  @actionBound
  setSource(value: this["source"] | undefined) {
    value = value ?? null;
    if (this.source === (value ?? null)) return;
    this.source = value;
    this.dirty = true;
  }

  @actionBound
  setSvgMarkerLibrary(value: this["svgMarkerLibrary"] | undefined) {
    value = value ?? null;
    this.svgMarkerLibrary = value;
    this.dirty = true;
  }

  @actionBound
  setSld(value: this["sld"]) {
    if (isEqual(this.sld, value)) return;
    this.sld = value;
    this.dirty = true;
  }

  @actionBound
  setCopyFrom(value: this["copyFrom"]) {
    this.copyFrom = value;
    this.dirty = true;
  }

  @actionBound
  setUploading(value: this["uploading"]) {
    this.uploading = value;
  }
}
