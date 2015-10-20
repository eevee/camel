Camel overview
==============

Camel is intended as a replacement for libraries like :py:mod:`pickle` or
`PyYAML`_, which automagically serialize any type they come across.  That seems
convenient at first, but in any large or long-lived application, the benefits
are soon outweighed by the costs:

.. _PyYAML: http://pyyaml.org/

* You can't move, rename, or delete any types that are encoded in a pickle.

* Even private implementation details of your class are encoded in a pickle by
  default, which means you can't change them either.

* Because pickle's behavior is recursive, it can be difficult to know which
  types are pickled.

* Because pickle's behavior is recursive, you may inadvertently pickle far more
  data than necessary, if your objects have caches or reified properties.  In
  extreme cases you may pickle configuration that's no longer correct when the
  pickle is loaded.

* Since pickles aren't part of your codebase and are rarely covered by tests,
  you may not know you've broken pickles until your code hits production...  or
  much later.

* Pickle in particular is very opaque, even when using the ASCII format.  It's
  easy to end up with a needlessly large pickle by accident and have no
  visibility into what's being stored in it, or to break loading a large pickle
  and be unable to recover gracefully or even tell where the problem is.

* Automagically serialized data is hard enough to load back into your *own*
  application.  Loading it anywhere else is effectively out of the question.

It's certainly possible to whip pickle or PyYAML into shape manually by writing
``__reduce__`` or representer functions, but their default behavior is still
automagic, so you can't be sure you didn't miss something.  Also, nobody
actually does it, so merely knowing it's possible doesn't help much.


Camel's philosophy
------------------

    Explicit is better than implicit.

    Complex is better than complicated.

    Readability counts.

    If the implementation is hard to explain, it's a bad idea.

    *In the face of ambiguity, refuse the temptation to guess.*

    — `The Zen of Python`_

    .. _The Zen of Python: https://www.python.org/dev/peps/pep-0020/

Serialization is hard.  We can't hide that difficulty, only delay it for a
while.  And it *will* catch up with you.

A few people in the Python community have been rallying against pickle and its
ilk for a while, but when asked for alternatives, all we can do is mumble
something about writing functions.  Well, that's not very helpful.

Camel forces you to write all your own serialization code, then wires it all
together for you.  It's backed by YAML, which is ostensibly easy for humans to
read — and has explicit support for custom types.  Hopefully, after using
Camel, you'll discover you've been tricked into making a library of every type
you serialize, the YAML name you give it, and exactly how it's formatted.  All
of this lives in your codebase, so someone refactoring a class will easily
stumble upon its serialization code.  Why, you could even use this knowledge to
load your types into an application written in a different language, or turn
them into a documented format!


Let's see some code already
---------------------------

Let's!

Here's the Table example from `a talk Alex Gaynor gave at PyCon US 2014`_.
Initially we have some square tables.

.. _a talk Alex Gaynor gave at PyCon US 2014: https://www.youtube.com/watch?v=7KnfGDajDQw&t=1292

.. code-block:: python

    class Table(object):
        def __init__(self, size):
            self.size = size

        def __repr__(self):
            return "<Table {self.size!r}>".format(self=self)

We want to be able to serialize these, so we write a *dumper* and a
corresponding *loader* function.  We'll also need a *registry* to store these
functions::

    from camel import CamelRegistry
    my_types = CamelRegistry()

    @my_types.dumper(Table, 'table', version=1)
    def _dump_table(table):
        return dict(
            size=table.size,
        )

    @my_types.loader('table', version=1)
    def _load_table(data, version):
        return Table(data["size"])

.. note:: This example is intended for Python 3.  With Python 2,
   ``dict(size=...)`` will create a "size" key that's a :py:class:`bytes`,
   which will be serialized as ``!!binary``.  It will still work, but it'll be
   ugly, and won't interop with Python 3.  If you're still on Python 2, you
   should definitely use dict literals with :py:class:`unicode` keys.

Now we just give this registry to a :py:class:`Camel` object and ask it to dump
for us::

    from camel import Camel
    table = Table(25)
    print(Camel([my_types]).dump(table))

.. code-block:: yaml

    !table;1
    size: 25

Unlike the simple example given in the talk, we can also dump arbitrary
structures containing Tables with no extra effort::

    data = dict(chairs=[], tables=[Table(25), Table(36)])
    print(Camel([my_types]).dump(data))

.. code-block:: yaml

    chairs: []
    tables:
    - !table;1
      size: 25
    - !table;1
      size: 36

And load them back in::

    print(Camel([my_types]).load("[!table;1 {size: 100}]"))

.. code-block:: python

    [<Table 100>]

Versioning
..........

As you can see, all serialized Tables are tagged as ``!table;1``.  The
``table`` part is the argument we gave to ``@dumper`` and ``@loader``, and the
``1`` is the version number.

Version numbers mean that when the time comes to change your class, you don't
have anything to worry about.  Just write a new loader and dumper with a higher
version number, and fix the old loader to work with the new code::

    # Tables can be rectangles now!
    class Table(object):
        def __init__(self, height, width):
            self.height = height
            self.width = width

        def __repr__(self):
            return "<Table {self.height!r}x{self.width!r}>".format(self=self)

    @my_types.dumper(Table, 'table', version=2)
    def _dump_table_v2(table):
        return dict(
            height=table.height,
            width=table.width,
        )

    @my_types.loader('table', version=2)
    def _load_table_v2(data, version):
        return Table(data["height"], data["width"])

    @my_types.loader('table', version=1)
    def _load_table_v1(data, version):
        edge = data["size"] ** 0.5
        return Table(edge, edge)

    table = Table(7, 10)
    print(Camel([my_types]).dump(table))

.. code-block:: yaml

    !table;2
    height: 7
    width: 10


More on versions
----------------

Versions are expected to be positive integers, presumably starting at 1.
Whenever your class changes, you have two options:

1. Fix the dumper and loader to preserve the old format but work with the new
   internals.
2. Failing that, write new dumpers and loaders and bump the version.

One of the advantages of Camel is that your serialization code is nothing more
than functions returning Python structures, so it's very easily tested.  Even
if you end up with dozens of versions, you can write test cases for each
without ever dealing with YAML at all.

You might be wondering whether there's any point to having more than one
version of a dumper function.  By default, only the dumper with the highest
version for a type is used.  But it's possible you may want to stay
backwards-compatible with other code — perhaps an older version of your
application or library — and thus retain the ability to write out older
formats.  You can do this with :py:meth:`Camel.lock_version`::

    @my_types.dumper(Table, 'table', version=1)
    def _dump_table_v1(table):
        return dict(
            # not really, but the best we can manage
            size=table.height * table.width,
        )

    camel = Camel([my_types])
    camel.lock_version(Table, 1)
    print(camel.dump(Table(5, 7)))

.. code-block:: yaml

    !table;1
    size: 35

Obviously you might lose some information when round-tripping through an old
format, but sometimes it's necessary until you can fix old code.

Note that version locking only applies to dumping, not to loading.  For
loading, there are a couple special versions you can use.

Let's say you delete an old class whose information is no longer useful.  While
cleaning up all references to it, you discover it has Camel dumpers and
loaders.  What about all your existing data?  No problem!  Just use a version
of ``all`` and return a dummy object::

    class DummyData(object):
        def __init__(self, data):
            self.data = data

    @my_types.loader('deleted-type', version=all)
    def _load_deleted_type(data, version):
        return DummyData(data)

``all`` overrides *all* other loader versions (hence the name).  You might
instead want to use ``any``, which is a fallback for when the version isn't
recognized::

    @my_types.loader('table', version=any)
    def _load_table(data, version):
        if 'size' in data:
            # version 1
            edge = data['size'] ** 0.5
            return Table(edge, edge)
        else:
            # version 2?)
            return Table(data['height'], data['width'])

Versions must still be integers; a non-integer version will cause an immediate
parse error.

Going versionless
.................

You might be thinking that the version numbers everywhere are an eyesore, and
your data would be much prettier if it only used ``!table``.

Well, yes, it would.  But you'd lose your ability to bump the version, so you'd
have to be *very very sure* that your chosen format can be adapted to any
possible future changes to your class.

If you are, in fact, *very very sure*, then you can use a version of ``None``.
This is treated like an *infinite* version number, so it will always be used
when dumping (unless overridden by a version lock).

Similarly, an unversioned tag will look for a loader with a ``None`` version,
then fall back to ``all`` or ``any``.  The order versions are checked for is
thus:

* ``None``, if appropriate
* ``all``
* Numeric version, if appropriate
* ``any``

There are deliberately no examples of unversioned tags here.  Designing an
unversioned format requires some care, and a trivial documentation example
can't do it justice.


Supported types
---------------

By default, Camel knows how to load and dump all types in the `YAML type
registry`_ to their Python equivalents, which are as follows.

.. _YAML type registry: http://yaml.org/type/

===============     ========================================
YAML tag            Python type
===============     ========================================
``!!binary``        :py:class:`bytes`
``!!bool``          :py:class:`bool`
``!!float``         :py:class:`float`
``!!int``           :py:class:`int` (or :py:class:`long` on Python 2)
``!!map``           :py:class:`dict`
``!!merge``         —
``!!null``          :py:class:`NoneType`
``!!omap``          :py:class:`collections.OrderedDict`
``!!seq``           :py:class:`list` or :py:class:`tuple` (dump only)
``!!set``           :py:class:`set`
``!!str``           :py:class:`str` (:py:class:`unicode` on Python 2)
``!!timestamp``     :py:class:`datetime.date` or :py:class:`datetime.datetime` as appropriate
===============     ========================================

.. note:: PyYAML tries to guess whether a bytestring is "really" a string on
   Python 2, but Camel does not.  Serializing *any* bytestring produces an ugly
   base64-encoded ``!!binary`` representation.

   This is a **feature**.

The following additional types are loaded by default, but **not dumped**.  If
you want to dump these types, you can use the existing ``camel.PYTHON_TYPES``
registry.

======================  =====================================
YAML tag                Python type
======================  =====================================
``!!python/complex``    :py:class:`complex`
``!!python/frozenset``  :py:class:`frozenset`
``!!python/namespace``  :py:class:`types.SimpleNamespace` (Python 3.3+)
``!!python/tuple``      :py:class:`tuple`
======================  =====================================


Other design notes
------------------

* Camel will automatically use the C extension if available, and fall back to a
  Python implementation otherwise.  The PyYAML documentation says it doesn't
  have this behavior because there are some slight differences between the
  implementations, but fails to explain what they are.

* :py:meth:`Camel.load` is safe by default.  There is no calling of arbitrary
  functions or execution of arbitrary code just from loading data.  There is no
  "dangerous" mode.  PyYAML's ``!!python/object`` and similar tags are not
  supported.  (Unless you write your own loaders for them, of course.)

* There is no "OO" interface, where dumpers or loaders can be written as
  methods with special names.  That approach forces a class to have only a
  single representation, and more importantly litters your class with junk
  unrelated to the class itself.  Consider this a cheap implementation of
  traits.  You can fairly easily build support for this in your application if
  you really *really* want it.

* Yes, you may have to write a lot of boring code like this::

    @my_types.dumper(SomeType, 'sometype')
    def _dump_sometype(data):
        return dict(
            foo=data.foo,
            bar=data.bar,
            baz=data.baz,
            ...
        )

  I strongly encourage you *not* to do this automatically using introspection,
  which would defeat the point of using Camel.  If it's painful, step back and
  consider whether you really need to be serializing as much as you are, or
  whether your classes need to be so large.

* There's no guarantee that the data you get will actually be in the correct
  format for that version.  YAML is meant for human beings, after all, and
  human beings make mistakes.  If you're concerned about this, you could
  combine Camel with something like the `Colander`_ library.

  .. _Colander: http://docs.pylonsproject.org/projects/colander/en/latest/


Known issues
------------

Camel is a fairly simple wrapper around `PyYAML`_, and inherits many of its
problems.  Only YAML 1.1 is supported, not 1.2, so a handful of syntactic edge
cases may not parse correctly.  Loading and dumping are certainly slower and
more memory-intensive than pickle or JSON.  Unicode handling is slightly
clumsy.  Python-specific types use tags starting with ``!!``, which is supposed
for be for YAML's types only.

.. _PyYAML: http://pyyaml.org/

Formatting and comments are not preserved during a round-trip load and dump.
The `ruamel.yaml`_ library is a fork of PyYAML that solves this problem, but it
only works when using the pure-Python implementation, which would hurt Camel's
performance even more.  Opinions welcome.

.. _ruamel.yaml: https://pypi.python.org/pypi/ruamel.yaml

PyYAML has several features that aren't exposed in Camel yet: dumpers that work
on subclasses, loaders that work on all tags with a given prefix, and parsers
for plain scalars in custom formats.
