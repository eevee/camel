from camel import Camel, CamelRegistry, PYTHON_TYPES

import collections


# -----------------------------------------------------------------------------
# Setup stuff

class DieRoll(tuple):
    def __new__(cls, a, b):
        return tuple.__new__(cls, [a, b])

    def __repr__(self):
        return "DieRoll(%s,%s)" % self


reg = CamelRegistry()


@reg.dumper(DieRoll, '!roll')
def dump_dice(dumper, data):
    return "{}d{}".format(*data)


@reg.loader(DieRoll, '!roll')
def load_dice(dumper, data):
    # TODO enforce incoming data is a string?
    a, _, b = data.partition('d')
    return DieRoll(int(a), int(b))


# -----------------------------------------------------------------------------
# Tests proper

def test_odict():
    value = collections.OrderedDict([('a', 1), ('b', 2), ('c', 3)])
    camel = Camel()
    dumped = camel.dump(value)
    assert dumped == '!!omap\n- a: 1\n- b: 2\n- c: 3\n'
    assert camel.load(dumped) == value


def test_tuple():
    # TODO short list like this should be flow style
    value = (1, 2, 3)
    camel = Camel()
    dumped = camel.dump(value)
    assert dumped == '- 1\n- 2\n- 3\n'
    assert camel.load(dumped) == list(value)


def test_dieroll():
    # TODO possibly should tag this as !!python/tuple in some cases
    # TODO short list like this should be flow style
    value = DieRoll(3, 6)
    camel = Camel([reg])
    dumped = camel.dump(value)
    # TODO i don't know why this ... is here
    assert dumped == '!roll 3d6\n...\n'
    assert camel.load(dumped) == value


# Python types

def test_python_tuple():
    # TODO short list like this should be flow style
    value = (1, 2, 3)
    camel = Camel([PYTHON_TYPES])
    dumped = camel.dump(value)
    assert dumped == '!!python/tuple\n- 1\n- 2\n- 3\n'
    assert camel.load(dumped) == value


def test_python_complex():
    value = 3 + 4j
    camel = Camel([PYTHON_TYPES])
    dumped = camel.dump(value)
    # TODO superfluous ... again
    assert dumped == '!!python/complex 3+4j\n...\n'
    assert camel.load(dumped) == value


def test_python_frozenset():
    value = frozenset(('x', 'y', 'z'))
    camel = Camel([PYTHON_TYPES])
    dumped = camel.dump(value)
    assert dumped == '!!python/frozenset\n- x\n- y\n- z\n'
    assert camel.load(dumped) == value
