NextGISWeb QGIS
===============

Installation to virtualenv
--------------------------

Requirements:

* Python virtualenv with nextgisweb installed
* QGIS 2.8 or higher

```
$ cd /path/to/ngw
$ git clone git@github.com:nextgis/nextgisweb_qgis.git
$ source env/bin/activate
$ pip install -e nextgisweb_qgis/
```

QGIS and PyQT4 dependencies are not listed in `setup.py` because it hard to install it in virtualenv. So lets copy this packages from system packages to virtualenv. On Ubuntu this libraries located in `python-sip`, `python-qt4` and `python-qgis` packages.

```
$ DST=`python -c "import sys; print sys.path[-1]"`
$ cp `/usr/bin/python -c "import sip; print sip.__file__"` $DST
$ cp -r `/usr/bin/python -c "import PyQt4, os.path; print os.path.split(PyQt4.__file__)[0]"` $DST
$ cp -r `/usr/bin/python -c "import qgis, os.path; print os.path.split(qgis.__file__)[0]"` $DST
```