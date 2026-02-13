import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";

import { FileUploader } from "@nextgisweb/file-upload/file-uploader";
import { assert } from "@nextgisweb/jsrealm/error";
import { useRoute } from "@nextgisweb/pyramid/hook";
import { gettext } from "@nextgisweb/pyramid/i18n";
import { resourceAttrItems } from "@nextgisweb/resource/api/resource-attr";
import { ResourceSelect } from "@nextgisweb/resource/component/resource-select";
import type { EditorWidget } from "@nextgisweb/resource/type";

import type { EditorStore } from "../EditorStore";

const msgUploadText = gettext("Select a style");
const msgHelpText = gettext("QML or SLD formats are supported.");
const msgSvgMarkerLibrary = gettext("SVG marker library");

export const FileModeComponent: EditorWidget<EditorStore> = observer(
    ({ store }) => {
        const [parentGroup, setParentGroup] = useState<number | undefined>(
            undefined
        );
        const resourceGroupId = store.composite?.parent;

        const { route } = useRoute("resource.attr");

        useEffect(() => {
            if (resourceGroupId !== undefined && resourceGroupId !== null) {
                const loadAttrItem = async () => {
                    const attrItems = await resourceAttrItems({
                        route,
                        resources: [resourceGroupId],
                        attributes: [["resource.parent"]],
                    });
                    const parent = attrItems[0].get("resource.parent");
                    if (parent) {
                        setParentGroup(parent.id);
                    }
                };
                loadAttrItem();
            }
        }, [resourceGroupId, route]);

        return (
            <>
                <FileUploader
                    accept=".qml,.sld"
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
