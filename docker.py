from ngwdocker import PackageBase
from ngwdocker.base import AppImage
from ngwdocker.util import git_ls_files


class Package(PackageBase):
    pass


@AppImage.on_apt.handler
def on_apt(event):
    event.command("apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 51F523511C7028C3")  # NOQA: E501
    event.add_repository("deb https://qgis.org/ubuntu-ltr bionic main")
    event.package(
        'build-essential', 'cmake',
        'libqgis-dev', 'qt5-image-formats-plugins',
    )


@AppImage.on_package_files.handler
def on_package_files(event):
    if event.package.name == 'nextgisweb_qgis':
        event.files.extend(git_ls_files(event.package.path / 'qgis_headless'))


@AppImage.on_virtualenv.handler
def on_virtualenv(event):
    event.before_install('$NGWROOT/env/bin/pip install --no-cache-dir package/nextgisweb_qgis/qgis_headless')  # NOQA: E501
