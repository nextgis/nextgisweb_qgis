from ngwdocker import PackageBase
from ngwdocker.base import AppImage


class Package(PackageBase):
    pass


@AppImage.on_apt.handler
def on_apt(event):
    event.command("apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 51F523511C7028C3")  # NOQA: E501
    event.add_repository("deb https://qgis.org/ubuntu bionic main")
    event.package('build-essential', 'cmake', 'libqgis-dev')
