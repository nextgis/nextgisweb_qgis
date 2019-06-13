import sys
import click

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
