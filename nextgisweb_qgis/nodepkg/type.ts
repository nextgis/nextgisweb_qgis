import type { FileMeta } from "@nextgisweb/file-upload/file-uploader";
import type { ResourceRef } from "@nextgisweb/resource/type/api";
import type { Style } from "@nextgisweb/sld/type/api";

export type Value = {
    file_upload?: FileMeta;
    svg_marker_library?: ResourceRef | null;
    format?: "default" | "sld";
    sld?: Style;
    copy_from?: ResourceRef;
};

export type Mode = "file" | "sld" | "copy" | "default";
