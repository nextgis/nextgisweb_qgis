# NextGIS Web QGIS renderer

## Installation

Starting from ``2.0.0`` this package requires QGIS 3.10+. If you need QGIS 2.18
compatible version check out ``1.3.x`` branch.

First of all, clone the repository with submodules:

```bash
$ cd package
$ git clone --recurse-submodules git@github.com:nextgis/nextgisweb_qgis.git
```

Then install `qgis_headless` which is included as git submodule and requires
QGIS 3.10+ and some additional libraries (see qgis_headeless/README.md for
details).

```bash
$ cd nextgisweb_qgis
$ pip install -e qgis_headless
```

Finally, install ``nextgisweb_qgis`` into virtualenv:

```bash
$ pip install -e ./
```