define([
    "dojo/_base/declare",
    "dojo/_base/lang",
    "dijit/_TemplatedMixin",
    "dijit/_WidgetsInTemplateMixin",
    "dijit/layout/ContentPane",
    "@nextgisweb/pyramid/i18n!",
    "ngw-resource/serialize",
    // resource
    "dojo/text!./template/QgisRasterStyleWidget.hbs",
    // template
    "dojox/layout/TableContainer",
    "ngw-file-upload/Uploader"
], function (
    declare,
    lang,
    _TemplatedMixin,
    _WidgetsInTemplateMixin,
    ContentPane,
    i18n,
    serialize,
    template
) {
    return declare([ContentPane, serialize.Mixin, _TemplatedMixin, _WidgetsInTemplateMixin], {
        templateString: i18n.renderTemplate(template),
        title: i18n.gettext("QGIS style"),
        prefix: "qgis_raster_style",

        serializeInMixin: function (data) {
            var prefix = this.prefix,
                setObject = function (key, value) { lang.setObject(prefix + "." + key, value, data); };

            setObject("file_upload", this.wFileUpload.get("value"));
        },

        validateDataInMixin: function (errback) {
            return this.wFileUpload.upload_promise === undefined
                || this.wFileUpload.upload_promise.isResolved();
        }

    });
});
