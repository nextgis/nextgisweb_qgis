import type { RasterSymbolizer } from "@nextgisweb/sld/style-editor/type/Style";

export function getSymbolizerValues(symbolizer: RasterSymbolizer) {
    if (!symbolizer) {
        return {
            redChannelMin: 0,
            redChannelMax: 255,
            greenChannelMin: 0,
            greenChannelMax: 255,
            blueChannelMin: 0,
            blueChannelMax: 255,
            redChannel: 0,
            greenChannel: 0,
            blueChannel: 0,
        };
    } else {
        const values = {};
        values["redChannelMin"] =
            symbolizer.channels.red.contrast_enhancement.normalize.min_value;
        values["redChannelMax"] =
            symbolizer.channels.red.contrast_enhancement.normalize.max_value;
        values["greenChannelMin"] =
            symbolizer.channels.green.contrast_enhancement.normalize.min_value;
        values["greenChannelMax"] =
            symbolizer.channels.green.contrast_enhancement.normalize.max_value;
        values["blueChannelMin"] =
            symbolizer.channels.blue.contrast_enhancement.normalize.min_value;
        values["blueChannelMax"] =
            symbolizer.channels.blue.contrast_enhancement.normalize.max_value;
        values["redChannel"] = symbolizer.channels.red.source_channel;
        values["greenChannel"] = symbolizer.channels.green.source_channel;
        values["blueChannel"] = symbolizer.channels.blue.source_channel;
        return values;
    }
}
