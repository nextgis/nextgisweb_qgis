import sys
import click

from ngwdocker import PackageBase

class Package(PackageBase):

    def options(self, func):
        func = click.option('--qgis-ppa', is_flag=True, help="Use QGIS PPA")(func)
        return func

    def debpackages(self):
        return (
            'qgis',
            'python-qgis',
            'python-sip',
            'python-qt4',
        )

    def envsetup(self):
        self.dockerfile.write(
            'COPY package/nextgisweb_qgis/qgis-to-env /opt/ngw/build/nextgisweb_qgis-qgis-to-env',
            'RUN /opt/ngw/build/nextgisweb_qgis-qgis-to-env /opt/ngw/env',
        )
