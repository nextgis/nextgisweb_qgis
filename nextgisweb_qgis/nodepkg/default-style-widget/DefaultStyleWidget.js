import { Button } from "@nextgisweb/gui/antd";
import { errorModal } from "@nextgisweb/gui/error";
import { route, routeURL } from "@nextgisweb/pyramid/api";
import i18n from "@nextgisweb/pyramid/i18n!qgis";

async function create({ cls, parentId, displayName }) {
    let data;
    try {
        data = await route("resource.collection").post({
            json: {
                resource: {
                    cls: cls,
                    display_name: displayName,
                    parent: { id: parentId },
                },
            },
        });
    } catch (error) {
        errorModal(error);
        return;
    }
    window.open(routeURL("resource.show", { id: data.id }), "_self");
}

export function DefaultStyleWidget(props) {
    return (
        <>
            <p style={{ maxWidth: "40em" }}>
                {i18n.gettext(
                    "Layer created. You need a style to add it to a web map. Use the button bellow to create a default QGIS style or create a style resource using sidebar."
                )}
            </p>
            <Button type="primary" onClick={() => create(props)}>
                {i18n.gettext("Create default QGIS style")}
            </Button>
        </>
    );
}
