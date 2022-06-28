from random import Random

from nextgisweb.i18n import trstring_factory

COMP_ID = 'qgis'
_ = trstring_factory(COMP_ID)


def rand_color(seed=None):
    r = Random(seed)
    return (r.randrange(0, 256, 1), r.randrange(0, 256, 1), r.randrange(0, 256, 1))
