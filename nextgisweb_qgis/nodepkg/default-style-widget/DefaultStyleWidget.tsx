import { Balancer } from "react-wrap-balancer";

import { Button, Card } from "@nextgisweb/gui/antd";
import { errorModal } from "@nextgisweb/gui/error";
import { route, routeURL } from "@nextgisweb/pyramid/api";
import { gettext } from "@nextgisweb/pyramid/i18n";

// prettier-ignore
const [msgButton, msgText] = [
    gettext("Create default QGIS style"),
    gettext("Layer created. You need a style to add it to a web map. Use the button bellow to create a default QGIS style or create a style resource using sidebar."),
]

export function DefaultStyleWidget({ payload }: { payload: unknown }) {
    const create = async () => {
        try {
            const { id } = (await route("resource.collection").post({
                json: payload,
            })) as { id: number };
            window.open(routeURL("resource.show", { id }), "_self");
        } catch (error) {
            errorModal(error);
            return;
        }
    };

    return (
        <Card size="small">
            <div
                style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "12px",
                }}
            >
                <Balancer ratio={0.62}>{msgText}</Balancer>
                <Button type="primary" onClick={() => create()}>
                    {msgButton}
                </Button>
            </div>
        </Card>
    );
}
