import { useMemo } from "react";

import { errorModal } from "@nextgisweb/gui/error";
import { route, routeURL } from "@nextgisweb/pyramid/api";
import { gettext } from "@nextgisweb/pyramid/i18n";
import { ResourceSectionButton } from "@nextgisweb/resource/resource-section";
import type {
    ResourceSection,
    ResourceSectionProps,
} from "@nextgisweb/resource/resource-section";
import type { CompositeCreate } from "@nextgisweb/resource/type/api";

// prettier-ignore
const [msgButton, msgText] = [
    gettext("Create default QGIS style"),
    gettext("Layer created. A style is required to add the layer to a web map. You can generate a default QGIS style resource using the button."),
]

interface QgisResourceSectionDefaultStyleProps extends ResourceSectionProps {
    payload: CompositeCreate;
}

export const QgisResourceSectionDefaultStyle: ResourceSection<
    QgisResourceSectionDefaultStyleProps
> = ({ payload }) => {
    const create = useMemo(
        () => async () => {
            try {
                const { id } = await route("resource.collection").post({
                    json: payload,
                });
                window.open(routeURL("resource.show", { id }), "_self");
            } catch (err) {
                errorModal(err);
                return;
            }
        },
        [payload]
    );

    return (
        <ResourceSectionButton
            type="primary"
            label={msgButton}
            onClick={create}
        >
            {msgText}
        </ResourceSectionButton>
    );
};

QgisResourceSectionDefaultStyle.displayName = "QgisResourceSectionDefaultStyle";
