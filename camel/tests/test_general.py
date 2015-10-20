# encoding: utf8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import collections
import datetime

import pytest

from camel import Camel, CamelRegistry, PYTHON_TYPES


# Round-trips for simple values of built-in types
@pytest.mark.parametrize(('value', 'expected_serialization'), [
    # TODO the trailing ... for non-container values is kinda weird
    (None, "null\n...\n"),
    ('ⓤⓝⓘⓒⓞⓓⓔ', "ⓤⓝⓘⓒⓞⓓⓔ\n...\n"),
    (b'bytes', "!!binary |\n  Ynl0ZXM=\n"),
    (True, "true\n...\n"),
    (133, "133\n...\n"),
    # long, for python 2
    (2**133, "10889035741470030830827987437816582766592\n...\n"),
    (3.52, "3.52\n...\n"),
    ([1, 2, 'three'], "- 1\n- 2\n- three\n"),
    ({'x': 7, 'y': 8, 'z': 9}, "x: 7\ny: 8\nz: 9\n"),
    # TODO this should use ? notation
    (set("qvx"), "!!set\nq: null\nv: null\nx: null\n"),
    (datetime.date(2015, 10, 21), "2015-10-21\n...\n"),
    (datetime.datetime(2015, 10, 21, 4, 29), "2015-10-21 04:29:00\n...\n"),
    # TODO case with timezone...  unfortunately can't preserve the whole thing
    (collections.OrderedDict([('a', 1), ('b', 2), ('c', 3)]), "!!omap\n- a: 1\n- b: 2\n- c: 3\n"),
])
def test_basic_roundtrip(value, expected_serialization):
    camel = Camel()
    dumped = camel.dump(value)
    assert dumped == expected_serialization
    assert camel.load(dumped) == value


def test_tuple_roundtrip():
    # By default, tuples become lists
    value = (4, 3, 2)
    camel = Camel()
    dumped = camel.dump(value)
    # TODO short list like this should be flow style?
    assert dumped == "- 4\n- 3\n- 2\n"
    assert camel.load(dumped) == list(value)


def test_frozenset_roundtrip():
    # By default, frozensets become sets
    value = frozenset((4, 3, 2))
    camel = Camel()
    dumped = camel.dump(value)
    # TODO this should use ? notation
    assert dumped == "!!set\n2: null\n3: null\n4: null\n"
    assert camel.load(dumped) == set(value)


# Round-trips for built-in Python types with custom representations
@pytest.mark.parametrize(('value', 'expected_serialization'), [
    ((4, 3, 2), "!!python/tuple\n- 4\n- 3\n- 2\n"),
    (5 + 12j, "!!python/complex 5+12j\n...\n"),
    (2j, "!!python/complex 2j\n...\n"),
    (frozenset((4, 3, 2)), "!!python/frozenset\n- 2\n- 3\n- 4\n"),
])
def test_python_roundtrip(value, expected_serialization):
    camel = Camel([PYTHON_TYPES])
    dumped = camel.dump(value)
    assert dumped == expected_serialization

    # Should be able to load them without the python types
    vanilla_camel = Camel()
    assert vanilla_camel.load(dumped) == value


# -----------------------------------------------------------------------------
# Simple custom type

class DieRoll(tuple):
    def __new__(cls, a, b):
        return tuple.__new__(cls, [a, b])

    def __repr__(self):
        return "DieRoll(%s,%s)" % self


reg = CamelRegistry()


@reg.dumper(DieRoll, 'roll', version=None)
def dump_dice(data):
    return "{}d{}".format(*data)


@reg.loader('roll', version=None)
def load_dice(data, version):
    # TODO enforce incoming data is a string?
    a, _, b = data.partition('d')
    return DieRoll(int(a), int(b))


def test_dieroll():
    value = DieRoll(3, 6)
    camel = Camel([reg])
    dumped = camel.dump(value)
    assert dumped == '!roll 3d6\n...\n'
    assert camel.load(dumped) == value
