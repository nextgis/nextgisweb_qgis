# NextGIS Web QGIS renderer

## Installation

First of all, clone the repository with submodules:

```bash
$ cd package
$ git clone --recurse-submodules git@github.com:nextgis/nextgisweb_qgis.git
```

Then install `qgis_headless` which is included as git submodule and requires
QGIS 3.22+ and some additional libraries (see qgis_headeless/README.md for
details).

```bash
$ cd nextgisweb_qgis
$ pip install -e qgis_headless
```

Finally, install `nextgisweb_qgis` into virtualenv:

```bash
$ pip install -e ./
```

## Styles compatibility

Since original QGIS libraries do render layers in this extension, most styling
and rendering options work well. However, there is a big difference between QGIS
and NextGIS Web in how they compose layers. QGIS renders layers together and
places labels on top of all layers. On the other hand, NextGIS Web renders
layers one-by-one (or even tile-by-tile) and stacks them together on a client
side. That's why, NextGIS Web rendering of QGIS styles may differ in the
following ways:

-   Blending options don't work;
-   Labels from diffenent layers may overlap;
-   Expression-driven SVG markers don't work;
-   Masking doesn't work at all, as it part of a project, not of a layer.

Some rendering features require special handling on QGIS Headless library side
and aren't implemented yet:

-   Variables, like `@mascale`
-   Gradients-based fills
-   Labels with external SVG markers
