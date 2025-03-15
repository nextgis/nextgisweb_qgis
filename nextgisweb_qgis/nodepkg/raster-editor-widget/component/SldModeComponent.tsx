import { observer } from "mobx-react-lite";
import { useCallback, useMemo } from "react";

import type { EditorWidget } from "@nextgisweb/resource/type";
import { RasterStyleEditor } from "@nextgisweb/sld/style-editor/RasterStyleEditor";
import type { Symbolizer } from "@nextgisweb/sld/style-editor/type/Style";
import type { RasterSymbolizer } from "@nextgisweb/sld/type/api";

import type { EditorStore } from "../EditorStore";

export const SldModeComponent: EditorWidget<EditorStore> = observer(
    ({ store }) => {
        const { sld } = store;

        const symbolizer_ = useMemo(() => sld?.rules[0]?.symbolizers[0], [sld]);

        const onChange = useCallback(
            (val: Symbolizer) =>
                store.setSld({ rules: [{ symbolizers: [val] }] }),
            [store]
        );

        return (
            <RasterStyleEditor
                initSymbolizer={symbolizer_ as RasterSymbolizer}
                onChange={onChange}
                resourceId={store.parent_id}
            />
        );
    }
);

SldModeComponent.displayName = "SldModeComponent";
