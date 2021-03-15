NextGISWeb QGIS
===============

Installation to virtualenv
--------------------------

Requirements:

* Python 2.7 virtualenv with nextgisweb installed (Python 3 is not supported in this version)
* QGIS 2.x (2.8 or higher, but not QGIS 3.x which is Python 3 only)

```
$ cd /path/to/ngw
$ git clone git@github.com:nextgis/nextgisweb_qgis.git
$ source env/bin/activate
$ pip install -e nextgisweb_qgis/
```

QGIS and PyQT4 dependencies are not listed in `setup.py` because it hard to install it in virtualenv. So lets copy this packages from system packages to virtualenv. On Ubuntu this libraries located in `qgis`, `python-sip`, `python-qt4` and `python-qgis` packages.

```
$ qgis-to-env env
```

uWSGI Deployment Notes
----------------------

You have to add `--lazy-apps` to the command line, in this way application will be loaded after master's fork, so each worker will get its thread.

```
[uwsgi]
lazy-apps = True
```

Beware as there is an older options named `lazy` that is way more invasive and highly discouraged (it is still here only for backward compatibility).

If you get an error message `ERROR: Auth db directory path could not be created` then you have to specify directory where an existing qgis-auth.db is located or created if not present.
This directory needs to be writeable by uwsgi process user. For example:

```
[uwsgi]
env = QGIS_AUTH_DB_DIR_PATH=/var/www
```

If you don't see cyrillic labels add the following environment variable:

```
environment = LC_ALL="en_US.UTF-8"
```

License
-------------
This program is licensed under GNU GPL v2 or any later version

Commercial support
----------
Need to fix a bug or add a feature to NextGISWeb QGIS? We provide custom development and support for this software. [Contact us](http://nextgis.ru/en/contact/) to discuss options!

[![http://nextgis.com](http://nextgis.ru/img/nextgis.png)](http://nextgis.com)
