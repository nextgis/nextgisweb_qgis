import { isEqual } from "lodash-es";
import { action, computed, observable } from "mobx";

import type {
  QgisRasterStyleRead,
  QgisRasterStyleUpdate,
  QgisVectorStyleRead,
  QgisVectorStyleUpdate,
} from "@nextgisweb/qgis/type/api";
import type { CompositeStore } from "@nextgisweb/resource/composite";
import type { EditorStore as IEditorStore } from "@nextgisweb/resource/type";

import { normalizePostprocess, serializePostprocess } from "../postprocess";
import type { PostprocessValue } from "../postprocess";

type ReadValue = QgisRasterStyleRead | QgisVectorStyleRead;
type UpdateValue = QgisRasterStyleUpdate | QgisVectorStyleUpdate;

interface EffectsStoreOptions {
  composite: CompositeStore;
  identity: "qgis_raster_style" | "qgis_vector_style";
}

export class EditorStore implements IEditorStore<
  ReadValue,
  UpdateValue,
  UpdateValue
> {
  readonly composite: CompositeStore;
  readonly identity: EffectsStoreOptions["identity"];

  @observable.ref accessor postprocess: PostprocessValue | null = null;

  #loaded: PostprocessValue | null = null;

  constructor({ composite, identity }: EffectsStoreOptions) {
    this.composite = composite;
    this.identity = identity;
  }

  @action
  load(value: ReadValue) {
    const normalized = normalizePostprocess(value.postprocess);
    this.postprocess = normalized;
    this.#loaded = normalized;
  }

  dump(): UpdateValue | undefined {
    if (!this.dirty) {
      return undefined;
    }

    return { postprocess: serializePostprocess(this.postprocess) };
  }

  @computed
  get dirty() {
    return !isEqual(this.postprocess, this.#loaded);
  }

  @computed
  get isValid(): boolean {
    return true;
  }

  @action.bound
  setPostprocess<K extends keyof PostprocessValue>(
    key: K,
    value: PostprocessValue[K]
  ) {
    const current: Partial<PostprocessValue> = this.postprocess ?? {};
    if (current[key] === value) return;
    this.postprocess = normalizePostprocess({ ...current, [key]: value });
  }
}
