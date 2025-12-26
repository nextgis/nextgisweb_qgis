import { observer } from "mobx-react-lite";
import { useCallback, useMemo } from "react";

import type { FeatureLayerGeometryType } from "@nextgisweb/feature-layer/type/api";
import type { EditorWidget } from "@nextgisweb/resource/type";
import { StyleEditor } from "@nextgisweb/sld/style-editor";
import { SymbolizerCard } from "@nextgisweb/sld/style-editor/component/SymbolizerCard";
import type {
    Symbolizer,
    SymbolizerType,
} from "@nextgisweb/sld/style-editor/type/Style";

import type { EditorStore } from "../EditorStore";

const GeometryToStyleTypeMap: Record<FeatureLayerGeometryType, SymbolizerType> =
    {
        "POINT": "point",
        "LINESTRING": "line",
        "POLYGON": "polygon",
        "MULTIPOINT": "point",
        "MULTILINESTRING": "line",
        "MULTIPOLYGON": "polygon",
        "POINTZ": "point",
        "LINESTRINGZ": "line",
        "POLYGONZ": "polygon",
        "MULTIPOINTZ": "point",
        "MULTILINESTRINGZ": "line",
        "MULTIPOLYGONZ": "polygon",
    };

export const SldModeComponent: EditorWidget<EditorStore> = observer(
    ({ store }) => {
        const { sld } = store;

        const symbolizer = useMemo(() => sld?.rules[0]?.symbolizers[0], [sld]);

        const onChange = useCallback(
            (val: Symbolizer) =>
                store.setSld({ rules: [{ symbolizers: [val] }] }),

            [store]
        );

        const initType: SymbolizerType = store.geometryType
            ? GeometryToStyleTypeMap[store.geometryType]
            : "point";

        return (
            <>
                {symbolizer && <SymbolizerCard symbolizer={symbolizer} />}

                <StyleEditor
                    value={symbolizer}
                    onChange={onChange}
                    initType={initType}
                />
            </>
        );
    }
);

SldModeComponent.displayName = "SldModeComponent";
