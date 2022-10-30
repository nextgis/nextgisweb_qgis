from random import Random

from nextgisweb.lib.i18n import trstr_factory

COMP_ID = 'qgis'
_ = trstr_factory(COMP_ID)


def rand_color(seed=None):
    r = Random(seed)
    return (r.randrange(0, 256, 1), r.randrange(0, 256, 1), r.randrange(0, 256, 1))
