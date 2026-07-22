import { observer } from "mobx-react-lite";
import { useCallback, useState } from "react";

import { Button, Input, Space } from "@nextgisweb/gui/antd";
import { gettext } from "@nextgisweb/pyramid/i18n";
import { route } from "@nextgisweb/pyramid/api";
import type { EditorWidget } from "@nextgisweb/resource/type";

import type { EditorStore } from "../EditorStore";

const msgPromptPlaceholder = gettext("Describe the style in plain language...");
const msgGenerate = gettext("Generate");

export const AiModeComponent: EditorWidget<EditorStore> = observer(
  ({ store }) => {
    const [prompt, setPrompt] = useState("");
    const [loading, setLoading] = useState(false);

    const resourceId = store.composite?.parent;

    const handleGenerate = useCallback(async () => {
      if (!resourceId || !prompt.trim()) return;

      setLoading(true);
      try {
        const result = await route(
          "qgis.style_generate",
          resourceId
        ).post({
          json: { prompt },
        });
        console.log("Generated FileUpload:", result);
      } catch (e) {
        console.error("Failed to generate QML", e);
      } finally {
        setLoading(false);
      }
    }, [resourceId, prompt]);

    return (
      <Space.Compact style={{ width: "100%" }}>
        <Input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={msgPromptPlaceholder}
          onPressEnter={handleGenerate}
        />
        <Button
          loading={loading}
          disabled={!prompt.trim()}
          onClick={handleGenerate}
        >
          {msgGenerate}
        </Button>
      </Space.Compact>
    );
  }
);

AiModeComponent.displayName = "AiModeComponent";
