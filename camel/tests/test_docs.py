"""Make sure the documentation examples actually, uh, work."""
from __future__ import unicode_literals
import textwrap


def test_docs_table_v1():
    class Table(object):
        def __init__(self, size):
            self.size = size

        def __repr__(self):
            return "<Table {self.size!r}>".format(self=self)

    from camel import CamelRegistry
    my_types = CamelRegistry()

    @my_types.dumper(Table, 'table', version=1)
    def _dump_table(table):
        return {
            'size': table.size,
        }

    @my_types.loader('table', version=1)
    def _load_table(data, version):
        return Table(data["size"])

    from camel import Camel
    table = Table(25)
    assert Camel([my_types]).dump(table) == "!table;1\nsize: 25\n"

    data = {'chairs': [], 'tables': [Table(25), Table(36)]}
    assert Camel([my_types]).dump(data) == textwrap.dedent("""
        chairs: []
        tables:
        - !table;1
          size: 25
        - !table;1
          size: 36
    """).lstrip()

    table, = Camel([my_types]).load("[!table;1 {size: 100}]")
    assert isinstance(table, Table)
    assert table.size == 100


def test_docs_table_v2():
    # Tables can be rectangles now!
    class Table(object):
        def __init__(self, height, width):
            self.height = height
            self.width = width

        def __repr__(self):
            return "<Table {self.height!r}x{self.width!r}>".format(self=self)

    from camel import Camel, CamelRegistry
    my_types = CamelRegistry()

    @my_types.dumper(Table, 'table', version=2)
    def _dump_table_v2(table):
        return {
            'height': table.height,
            'width': table.width,
        }

    @my_types.loader('table', version=2)
    def _load_table_v2(data, version):
        return Table(data["height"], data["width"])

    @my_types.loader('table', version=1)
    def _load_table_v1(data, version):
        edge = data["size"] ** 0.5
        return Table(edge, edge)

    table = Table(7, 10)
    assert Camel([my_types]).dump(table) == textwrap.dedent("""
        !table;2
        height: 7
        width: 10
    """).lstrip()

    @my_types.dumper(Table, 'table', version=1)
    def _dump_table_v1(table):
        return {
            # not really, but the best we can manage
            'size': table.height * table.width,
            }

    camel = Camel([my_types])
    camel.lock_version(Table, 1)
    assert camel.dump(Table(5, 7)) == "!table;1\nsize: 35\n"


def test_docs_deleted():
    class DummyData(object):
        def __init__(self, data):
            self.data = data

    from camel import Camel, CamelRegistry
    my_types = CamelRegistry()

    @my_types.loader('deleted-type', version=all)
    def _load_deleted_type(data, version):
        return DummyData(data)

    camel = Camel([my_types])
    assert isinstance(camel.load("""!deleted-type;4 foo"""), DummyData)


def test_docs_table_any():
    class Table(object):
        def __init__(self, height, width):
            self.height = height
            self.width = width

        def __repr__(self):
            return "<Table {self.height!r}x{self.width!r}>".format(self=self)

    from camel import Camel, CamelRegistry
    my_types = CamelRegistry()

    @my_types.loader('table', version=any)
    def _load_table(data, version):
        if 'size' in data:
            # version 1
            edge = data['size'] ** 0.5
            return Table(edge, edge)
        else:
            # version 2?)
            return Table(data['height'], data['width'])

    camel = Camel([my_types])
    table1, table2 = camel.load(
        "[!table;1 {size: 49}, !table;2 {height: 5, width: 9}]")

    assert table1.height == 7
    assert table1.width == 7
    assert table2.height == 5
    assert table2.width == 9
