from ngwdocker import PackageBase

class Package(PackageBase):

    def debpackages(self):
        return (
            'ngqgis',
            'python-ngqgis',
            'python-sip',
            'python-qt4',
        )

    def envsetup(self):
        self.dockerfile.write(
            'COPY package/nextgisweb_qgis/qgis-to-env /opt/ngw/build/nextgisweb_qgis-qgis-to-env',
            'RUN /opt/ngw/build/nextgisweb_qgis-qgis-to-env /opt/ngw/env',
        )

    def initialize(self):
        super().initialize()

        mod = self.context.packages['ngwdocker'].module
        app_img = mod.AppImage

        @app_img.on_apt.handler
        def on_apt(event):
            event.package('ngqgis', 'python-ngqgis', 'python-sip', 'python-qt4')

        @app_img.on_package_files.handler
        def on_package_files(event):
            if event.package == self:
                event.add(self.path / 'qgis-to-env')
        
        @app_img.on_virtualenv.handler
        def on_virtualenv(event):
            event.before_install('/opt/ngw/package/nextgisweb_qgis/qgis-to-env /opt/ngw/env')
