import { observer } from "mobx-react-lite";
import { useState } from "react";

import { gettext } from "@nextgisweb/pyramid/i18n";
import { EffectsPreview } from "@nextgisweb/render/effects-preview/EffectsPreview";
import type { EffectsPreviewMode } from "@nextgisweb/render/effects-preview/EffectsPreview";
import { PostprocessSection } from "@nextgisweb/render/postprocess-section/PostprocessSection";
import type { EditorWidget as IEditorWidget } from "@nextgisweb/resource/type";

import type { EditorStore } from "./EditorStore";
import { serializePostprocess } from "../postprocess";

import "./EditorWidget.less";

export const EditorWidget: IEditorWidget<EditorStore> = observer(
  ({ store }) => {
    const [previewMode, setPreviewMode] = useState<EffectsPreviewMode>("image");

    return (
      <div className="ngw-qgis-effects-widget">
        <PostprocessSection
          value={store.postprocess}
          onChange={(key, value) => store.setPostprocess(key, value)}
        />
        <EffectsPreview
          resourceId={store.composite.resourceId}
          postprocess={serializePostprocess(store.postprocess)}
          mode={previewMode}
          onModeChange={setPreviewMode}
        />
      </div>
    );
  }
);

EditorWidget.displayName = "EditorWidget";
EditorWidget.title = gettext("Effects");
EditorWidget.order = -49;
