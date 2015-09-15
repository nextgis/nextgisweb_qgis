define([
    "dojo/_base/declare",
    "dojo/_base/lang",
    "dojo/Deferred",
    "dojo/when",
    "dijit/_TemplatedMixin",
    "dijit/_WidgetsInTemplateMixin",
    "dijit/layout/ContentPane",
    "ngw-resource/serialize",
    // resource
    "dojo/text!./template/VectorStyleWidget.html",
    // template
    "dojox/layout/TableContainer",
    "ngw-file-upload/Uploader"
], function (
    declare,
    lang,
    Deferred,
    when,
    _TemplatedMixin,
    _WidgetsInTemplateMixin,
    ContentPane,
    serialize,
    template
) {
    return declare([ContentPane, serialize.Mixin, _TemplatedMixin, _WidgetsInTemplateMixin], {
        templateString: template,
        title: "QGIS vector style",
        prefix: "qgis_vector_style",

        serializeInMixin: function (data) {
            var prefix = this.prefix,
                setObject = function (key, value) { lang.setObject(prefix + "." + key, value, data); };

            setObject("file_upload", this.wFileUpload.get("value"));
        }
    });
});