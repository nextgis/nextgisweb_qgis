<%! from nextgisweb_qgis import QgisRasterStyle, QgisVectorStyle %>

<%
    cls = QgisRasterStyle.identity if QgisRasterStyle.check_parent(obj) \
        else QgisVectorStyle.identity
%>

<div id="DefaultStyleWidget"></div>

<script type="text/javascript">
    require([
        "@nextgisweb/qgis/default-style-widget",
        "@nextgisweb/gui/react-app",
    ], function (comp, reactApp) {
        reactApp.default(
            comp.default, {
                cls: "${cls}",
                parentId: ${obj.id},
                displayName: "${obj.display_name}",
            }, document.getElementById('DefaultStyleWidget')
        );
    });
</script>
