import { observer } from "mobx-react-lite";
import { useCallback } from "react";

import { Button, Input, Modal, Space, Spin } from "@nextgisweb/gui/antd";
import { errorModal } from "@nextgisweb/gui/error";
import { useUnsavedChanges } from "@nextgisweb/gui/hook";
import { route } from "@nextgisweb/pyramid/api";
import { gettext } from "@nextgisweb/pyramid/i18n";

import type { EditorStore } from "../EditorStore";

const { TextArea } = Input;

const msgTitle = gettext("Generate with AI");
const msgPromptPlaceholder = gettext("Describe the style in plain language...");
const msgGenerate = gettext("Generate");
const msgCancel = gettext("Cancel");

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

    useUnsavedChanges({ dirty: generating });

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
          generating ? null : (
            <Space>
              <Button onClick={onClose}>{msgCancel}</Button>
              <Button
                type="primary"
                disabled={!prompt.trim()}
                onClick={handleGenerate}
              >
                {msgGenerate}
              </Button>
            </Space>
          )
        }
      >
        {generating ? (
          <Spin size="large">
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
