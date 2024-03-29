import { observer } from "mobx-react-lite";

import { gettext } from "@nextgisweb/pyramid/i18n";
import { ResourceSelect } from "@nextgisweb/resource/component/";
import type { ResourceRef } from "@nextgisweb/resource/type/api";

const msgLabel = gettext("Source");

export const CopyFromComponent = observer(
    ({
        store,
        cls,
    }: {
        store: { setCopyFrom: (value: ResourceRef) => void };
        cls: "qgis_vector_style" | "qgis_raster_style";
    }) => {
        return (
            <>
                <label>{msgLabel}</label>
                <ResourceSelect
                    onChange={(value) => {
                        store.setCopyFrom({ id: value } as ResourceRef);
                    }}
                    pickerOptions={{ requireClass: cls }}
                />
            </>
        );
    }
);
