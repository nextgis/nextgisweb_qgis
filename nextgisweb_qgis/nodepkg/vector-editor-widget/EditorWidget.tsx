import { observer } from "mobx-react-lite";
import { useMemo } from "react";

import { Divider } from "@nextgisweb/gui/antd";
import { ModeSelector } from "@nextgisweb/gui/component";
import { gettext } from "@nextgisweb/pyramid/i18n";
import type { EditorWidget as IEditorWidget } from "@nextgisweb/resource/type";

import { CopyFromComponent } from "../CopyFromComponent";

import type { EditorStore, Mode } from "./EditorStore";
import { FileModeComponent } from "./component/FileModeComponent";
import { SldModeComponent } from "./component/SldModeComponent";

import "./EditorWidget.less";

export const EditorWidget: IEditorWidget<EditorStore> = observer(
  ({ store }) => {
    const modeOpts = [
      { value: "file" as Mode, label: gettext("Style from file") },
    ];
    if (store.geometryType !== "NONE") {
      modeOpts.push({
        value: "sld" as Mode,
        label: gettext("User-defined style"),
      });
    }
    modeOpts.push(
      ...[
        { value: "default" as Mode, label: gettext("Default style") },
        { value: "copy" as Mode, label: gettext("Copy from resource") },
      ]
    );

    const { mode } = store;

    const modeComponent = useMemo(() => {
      switch (mode) {
        case "file":
          return <FileModeComponent store={store} />;
        case "sld":
          return (
            <>
              <Divider />
              <SldModeComponent store={store} />
            </>
          );
        case "copy":
          return (
            <>
              <Divider />
              <CopyFromComponent store={store} cls="qgis_vector_style" />
            </>
          );
      }
    }, [store, mode]);

    return (
      <div className="ngw-qgis-vector-editor-widget">
        <ModeSelector<Mode>
          className="mode"
          value={store.mode}
          options={modeOpts}
          onChange={store.setMode}
        />
        {modeComponent}
      </div>
    );
  }
);

EditorWidget.displayName = "EditorWidget";
EditorWidget.title = gettext("QGIS style");
EditorWidget.activateOn = { create: true };
EditorWidget.order = -50;
