from importlib import import_module
from warnings import warn


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis.qgis"))


def __getattr__(name):
    ver = '2.8.0.dev1'
    cmp = 'qgis'
    pkg = f'nextgisweb_{cmp}'
    new = f'{pkg}.{cmp}'
    m = import_module(new)
    if hasattr(m, name):
        warn(
            f"Since {ver} {cmp} component has been moved to {new}. "
            f"Update import to {new}.{name}.", stacklevel=2)
        return getattr(m, name)

    raise AttributeError
