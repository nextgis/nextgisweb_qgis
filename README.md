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

uWSGI Deployment Notes
----------------------

You have to add `--lazy` to the command line, in this way application will be loaded after master's fork, so each worker will get its thread.

```
[uwsgi]
lazy = True
```

If you get an error message `ERROR: Auth db directory path could not be created` then you have to specify directory where an existing qgis-auth.db is located or created if not present.
This directory needs to be writeable by uwsgi process user. For example:

```
[uwsgi]
env = QGIS_AUTH_DB_DIR_PATH=/var/www
```

License
-------------
This program is licensed under GNU GPL v2 or any later version

Commercial support
----------
Need to fix a bug or add a feature to NextGISWeb QGIS? We provide custom development and support for this software. [Contact us](http://nextgis.ru/en/contact/) to discuss options!

[![http://nextgis.com](http://nextgis.ru/img/nextgis.png)](http://nextgis.com)
