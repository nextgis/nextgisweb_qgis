import { observer } from "mobx-react-lite";

import { gettext } from "@nextgisweb/pyramid/i18n";
import { ResourceSelect } from "@nextgisweb/resource/component/";
import type { EditorWidgetProps } from "@nextgisweb/resource/type";

import type { EditorStore } from "../EditorStore";
import type { CopyValue } from "../EditorStore";

const msgLabel = gettext("Source");

export const CopyModeComponent = observer(
    ({ store }: EditorWidgetProps<EditorStore>) => {
        return (
            <>
                <label>{msgLabel}</label>
                <ResourceSelect
                    onChange={(value) => {
                        store.setCopy({ id: value } as CopyValue);
                    }}
                    pickerOptions={{ requireClass: "qgis_raster_style" }}
                />
            </>
        );
    }
);
