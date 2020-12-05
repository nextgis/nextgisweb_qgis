from ngwdocker import PackageBase
from ngwdocker.base import AppImage


class Package(PackageBase):
    pass


@AppImage.on_apt.handler
def on_apt(event):
    if event.image.base != 'ubuntu:18.04':
        raise ValueError("Only ubuntu:18.04 base image is supported for nextgisweb_qgis!")
    event.package('ngqgis', 'python-ngqgis', 'python-sip', 'python-qt4')


@AppImage.on_package_files.handler
def on_package_files(event):
    if isinstance(event.package, Package):
        event.add(event.package.path / 'qgis-to-env')


@AppImage.on_virtualenv.handler
def on_virtualenv(event):
    event.before_install(
        '$NGWROOT/package/nextgisweb_qgis/qgis-to-env ' +
        '$NGWROOT/env')

