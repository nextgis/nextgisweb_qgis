import { observer } from "mobx-react-lite";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { FeatureLayerGeometryType } from "@nextgisweb/feature-layer/type/api";
import type { OptionType } from "@nextgisweb/gui/antd";
import { useResourceAttr } from "@nextgisweb/resource/hook/useResourceAttr";
import type { EditorWidget } from "@nextgisweb/resource/type";
import { StyleEditor } from "@nextgisweb/sld/style-editor";
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
    const { sld, composite } = store;

    const [fields, setFields] = useState<OptionType[] | undefined>(undefined);

    const symbolizer = useMemo(
      () => sld?.rules.flatMap((s) => s.symbolizers),
      [sld]
    );

    const { fetchResourceItems } = useResourceAttr();

    useEffect(() => {
      let canceled = false;
      const resourceId = composite?.parent;
      if (resourceId !== undefined && resourceId !== null) {
        fetchResourceItems({
          resources: [resourceId],
          attributes: [["feature_layer.fields"]],
        }).then((items) => {
          if (!canceled) {
            const fields = items[0].get("feature_layer.fields");
            setFields(
              fields
                ? fields.map((f) => ({
                    value: f.keyname,
                    label: f.display_name,
                  }))
                : undefined
            );
          }
        });
      }
      return () => {
        canceled = true;
      };
    }, [composite?.parent, fetchResourceItems]);

    const onChange = useCallback(
      (val: Symbolizer[]) =>
        store.setSld({
          rules: val.map((s) => ({
            symbolizers: [s],
          })),
        }),

      [store]
    );

    const initType: SymbolizerType = store.geometryType
      ? GeometryToStyleTypeMap[store.geometryType]
      : "point";

    return (
      <StyleEditor
        value={symbolizer}
        onChange={onChange}
        initType={initType}
        fields={fields}
      />
    );
  }
);

SldModeComponent.displayName = "SldModeComponent";
