import { observer } from "mobx-react-lite";
import { useState } from "react";

import { gettext } from "@nextgisweb/pyramid/i18n";
import { EffectsPreview } from "@nextgisweb/render/effects-preview/EffectsPreview";
import type { EffectsPreviewMode } from "@nextgisweb/render/effects-preview/EffectsPreview";
import {
  EffectsActions,
  PostprocessSection,
  useEffectsConfig,
} from "@nextgisweb/render/postprocess-section";
import type { EditorWidget as IEditorWidget } from "@nextgisweb/resource/type";

import { serializePostprocess } from "../postprocess";

import type { EditorStore } from "./EditorStore";

import "./EditorWidget.less";

export const EditorWidget: IEditorWidget<EditorStore> = observer(
  ({ store }) => {
    const [previewMode, setPreviewMode] = useState<EffectsPreviewMode>("image");
    const { defaults, presets } = useEffectsConfig();

    const handleToggle = () => {
      if (store.effectsEnabled) {
        store.disableEffects();
      } else {
        store.enableEffects(defaults);
      }
    };

    return (
      <div className="ngw-qgis-effects-widget">
        <EffectsActions
          enabled={store.effectsEnabled}
          canReset
          onToggle={handleToggle}
          onReset={() => store.resetEffects(defaults)}
        />
        {store.effectsEnabled ? (
          <>
            <PostprocessSection
              presets={presets}
              selectedPresetKey={store.selectedPresetKey}
              value={store.postprocess}
              onChange={(key, value) => store.setPostprocess(key, value)}
              onChangeValue={(value) => store.replacePostprocess(value)}
              onChangeSelectedPresetKey={(value) =>
                store.setSelectedPresetKey(value)
              }
            />
            <EffectsPreview
              resourceId={store.composite.resourceId}
              postprocess={serializePostprocess(store.postprocess)}
              mode={previewMode}
              onModeChange={setPreviewMode}
            />
          </>
        ) : null}
      </div>
    );
  }
);

EditorWidget.displayName = "EditorWidget";
EditorWidget.title = gettext("Effects");
EditorWidget.order = -49;
