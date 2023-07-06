from random import Random


def rand_color(seed=None):
    r = Random(seed)
    return (r.randrange(0, 256, 1), r.randrange(0, 256, 1), r.randrange(0, 256, 1))
