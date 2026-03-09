/** @plugin */
import { route } from "@nextgisweb/pyramid/api";
import { gettext } from "@nextgisweb/pyramid/i18n";
import { registerResourceAction } from "@nextgisweb/resource/resource-section/registry";

import ExportIcon from "@nextgisweb/icon/material/download";

registerResourceAction(COMP_ID, {
  key: "qml",
  icon: <ExportIcon />,
  label: gettext("QML file"),
  menu: { order: 0, group: "extra" },
  condition: (it) => {
    return (
      it.get("resource.cls") === "qgis_raster_style" ||
      it.get("resource.cls") === "qgis_vector_style"
    );
  },
  href: (it) => route("qgis.style_qml", it.id).url(),
});
