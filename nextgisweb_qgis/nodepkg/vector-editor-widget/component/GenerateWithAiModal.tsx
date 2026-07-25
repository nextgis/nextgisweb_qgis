import { observer } from "mobx-react-lite";
import { useCallback, useEffect } from "react";

import { Button, Input, Modal, Space, Spin } from "@nextgisweb/gui/antd";
import { errorModal } from "@nextgisweb/gui/error";
import { route } from "@nextgisweb/pyramid/api";
import { gettext } from "@nextgisweb/pyramid/i18n";

import type { EditorStore } from "../EditorStore";

const { TextArea } = Input;

const msgTitle = gettext("Generate with AI");
const msgPromptPlaceholder = gettext("Describe the style in plain language...");
const msgGenerate = gettext("Generate");
const msgCancel = gettext("Cancel");
const msgGenerating = gettext(
  "Please wait, the request is being processed by AI"
);

interface GenerateWithAiModalProps {
  store: EditorStore;
  resourceId: number;
  open: boolean;
  prompt: string;
  onPromptChange: (value: string) => void;
  onClose: () => void;
}

export const GenerateWithAiModal = observer(
  ({
    store,
    resourceId,
    open,
    prompt,
    onPromptChange,
    onClose,
  }: GenerateWithAiModalProps) => {
    const { uploading: generating } = store;

    useEffect(() => {
      if (!generating) return;
      const handler = (e: BeforeUnloadEvent) => {
        e.preventDefault();
      };
      window.addEventListener("beforeunload", handler);
      return () => window.removeEventListener("beforeunload", handler);
    }, [generating]);

    const handleGenerate = useCallback(async () => {
      if (!prompt.trim()) return;
      store.setUploading(true);
      try {
        const { file_upload } = await route(
          "qgis.style_generate",
          resourceId
        ).post({
          json: { prompt },
        });
        store.setSource({
          id: file_upload.id,
          name: file_upload.name ?? "style.qml",
          mime_type: file_upload.mime_type ?? "",
          size: file_upload.size,
        });
        onClose();
      } catch (err) {
        errorModal(err);
      } finally {
        store.setUploading(false);
      }
    }, [prompt, resourceId, store, onClose]);

    return (
      <Modal
        open={open}
        title={msgTitle}
        onCancel={generating ? undefined : onClose}
        closable={!generating}
        mask={{ closable: !generating }}
        width={640}
        footer={
          <Space>
            <Button onClick={onClose} disabled={generating}>
              {msgCancel}
            </Button>
            <Button
              type="primary"
              loading={generating}
              disabled={!prompt.trim()}
              onClick={handleGenerate}
            >
              {msgGenerate}
            </Button>
          </Space>
        }
      >
        {generating ? (
          <Spin size="large" description={msgGenerating}>
            <div style={{ height: 80 }} />
          </Spin>
        ) : (
          <TextArea
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            placeholder={msgPromptPlaceholder}
            rows={4}
            style={{ overflowY: "auto", resize: "none" }}
          />
        )}
      </Modal>
    );
  }
);

GenerateWithAiModal.displayName = "GenerateWithAiModal";
