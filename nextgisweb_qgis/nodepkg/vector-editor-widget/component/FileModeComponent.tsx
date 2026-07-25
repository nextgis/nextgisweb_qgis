import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";

import { FileUploader } from "@nextgisweb/file-upload/file-uploader";
import { Button } from "@nextgisweb/gui/antd";
import { assert } from "@nextgisweb/jsrealm/error";
import llmSettings from "@nextgisweb/llm-core/client-settings";
import { useRoute } from "@nextgisweb/pyramid/hook";
import { gettext } from "@nextgisweb/pyramid/i18n";
import { resourceAttrItems } from "@nextgisweb/resource/api/resource-attr";
import { ResourceSelect } from "@nextgisweb/resource/component/resource-select";
import type { EditorWidget } from "@nextgisweb/resource/type";

import type { EditorStore } from "../EditorStore";

import { GenerateWithAiModal } from "./GenerateWithAiModal";

const msgUploadText = gettext("Select a style");
const msgHelpText = gettext("QML or SLD formats are supported.");
const msgSvgMarkerLibrary = gettext("SVG marker library");
const msgGenerateWithAi = gettext("Generate with AI");

export const FileModeComponent: EditorWidget<EditorStore> = observer(
  ({ store }) => {
    const [parentGroup, setParentGroup] = useState<number | undefined>(
      undefined
    );
    const resourceId = store.composite?.parent;

    const [aiModalOpen, setAiModalOpen] = useState(false);
    const [aiPrompt, setAiPrompt] = useState("");

    const { route } = useRoute("resource.attr");

    useEffect(() => {
      if (resourceId !== undefined && resourceId !== null) {
        const loadAttrItem = async () => {
          const attrItems = await resourceAttrItems({
            route,
            resources: [resourceId],
            attributes: [["resource.parent"]],
          });
          const parent = attrItems[0].get("resource.parent");
          if (parent) {
            setParentGroup(parent.id);
          }
        };
        loadAttrItem();
      }
    }, [resourceId, route]);

    return (
      <>
        <div className="file-uploader-wrap">
          <FileUploader
            accept=".qml,.sld"
            fileMeta={store.source ?? undefined}
            onChange={(value) => {
              assert(!Array.isArray(value));
              store.setSource(value);
            }}
            onUploading={(value) => {
              store.setUploading(value);
            }}
            uploadText={msgUploadText}
            helpText={msgHelpText}
          />
          {llmSettings.available && resourceId !== null && (
            <Button
              className="generate-with-ai-button"
              size="small"
              onClick={() => setAiModalOpen(true)}
            >
              {msgGenerateWithAi}
            </Button>
          )}
        </div>
        {resourceId && (
          <GenerateWithAiModal
            store={store}
            resourceId={resourceId}
            open={aiModalOpen}
            prompt={aiPrompt}
            onPromptChange={setAiPrompt}
            onClose={() => setAiModalOpen(false)}
          />
        )}
        <label>{msgSvgMarkerLibrary}</label>
        <ResourceSelect
          value={store.svgMarkerLibrary ?? undefined}
          onChange={(value) => {
            assert(!Array.isArray(value));
            store.setSvgMarkerLibrary(value);
          }}
          pickerOptions={{
            traverseClasses: ["resource_group"],
            requireClass: "svg_marker_library",
            initParentId: parentGroup,
            hideUnavailable: true,
          }}
          allowClear
        />
      </>
    );
  }
);

FileModeComponent.displayName = "FileModeComponent";
