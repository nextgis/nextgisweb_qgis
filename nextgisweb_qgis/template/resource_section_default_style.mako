<%!
    from nextgisweb.resource import Resource
    from nextgisweb_qgis import QgisRasterStyle, QgisVectorStyle
%>

<%page args="section, cls" />
<% section.content_box = False %>

<%
    child = Resource.registry[cls](parent=obj, owner_user=request.user)
    sdn = child.suggest_display_name(request.localizer.translate)
    payload = dict(resource=dict(cls=cls, parent=dict(id=obj.id), display_name=sdn))
%>

<div id="DefaultStyleWidget"></div>

<script type="text/javascript">
    ngwEntry("@nextgisweb/gui/react-boot").then(({ default: reactBoot}) => {
        reactBoot(
            "@nextgisweb/qgis/default-style-widget",
            {payload: ${json_js(payload)}},
            "DefaultStyleWidget"
        );
    });
</script>
