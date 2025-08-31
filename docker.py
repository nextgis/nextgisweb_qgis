from ngwdocker import PackageBase
from ngwdocker.base import AppImage
from ngwdocker.util import git_ls_files


class Package(PackageBase):
    pass


@AppImage.on_apt.handler
def on_apt(event):
    if event.image.package.apt_repository.get("nextgis_rm"):
        event.package("libngqgis-dev", "ngqgis-providers-common")
    else:
        event.add_repository("deb https://qgis.org/ubuntu-ltr $(lsb_release -sc) main")
        event.add_key("https://download.qgis.org/downloads/qgis-2022.gpg.key")
        # Package qgis-providers-common is required to get standard icons working.
        # TODO: Don't install package with its dependecies, just download it and
        # extract files to /usr/share/qgis/svg
        event.package("libqgis-dev", "qgis-providers-common")

    event.package(
        "build-essential",
        "cmake",
        "qt5-image-formats-plugins",
    )


@AppImage.on_package_files.handler
def on_package_files(event):
    if event.package.name == "nextgisweb_qgis":
        event.files.extend(git_ls_files(event.package.path / "qgis_headless"))


@AppImage.on_virtualenv.handler
def on_virtualenv(event):
    event.before_install(
        f"{event.path}/bin/pip install --no-cache-dir package/nextgisweb_qgis/qgis_headless"
    )


@AppImage.on_config.handler
def on_config(event):
    event.image.config_set("qgis", "svg_path", "/usr/share/qgis/svg")
    event.image.config_set("qgis", "test.qgis_headless_path", "/opt/ngw/package/nextgisweb_qgis")
