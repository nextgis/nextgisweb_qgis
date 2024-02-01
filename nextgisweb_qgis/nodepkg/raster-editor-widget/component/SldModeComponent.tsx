import { observer } from "mobx-react-lite";
import { useCallback, useMemo } from "react";

import type { EditorWidgetProps } from "@nextgisweb/resource/type";
import { RasterStyleEditor } from "@nextgisweb/sld/style-editor/RasterStyleEditor";
import type {
    RasterSymbolizer,
    Symbolizer,
} from "@nextgisweb/sld/style-editor/type/Style";

import type { EditorStore } from "../EditorStore";

export const SldModeComponent = observer(
    ({ store }: EditorWidgetProps<EditorStore>) => {
        const { sld } = store;

        const symbolizer_ = useMemo(
            () => sld?.rules[0]?.symbolizers[0],
            [sld]
        ) as RasterSymbolizer;
        const resourceId = store.composite.parent;

        const onChange = useCallback(
            (val: Symbolizer) =>
                store.setSld({ rules: [{ symbolizers: [val] }] }),
            [store]
        );

        return (
            <RasterStyleEditor
                initSymbolizer={symbolizer_}
                onChange={onChange}
                resourceId={resourceId}
            />
        );
    }
);
