Brief YAML reference
====================

There is no official YAML reference guide.  The YAML website only offers the
`YAML specification`_, which is a dense and thorny tome clearly aimed at
implementers.  I suspect this has greatly hampered YAML's popularity.

.. _YAML specification: http://www.yaml.org/spec/1.2/spec.html

In the hopes of improving this situation, here is a very quick YAML overview
that should describe the language almost entirely.  Hopefully it's useful
whether or not you use Camel.


Overall structure and design
----------------------------

As I see it, YAML has two primary goals: to support encoding any arbitrary data
structure; and to be easily read and written by humans.  If only the spec
shared that last goal.

Human-readability means that much of YAML's syntax is optional, wherever it
would be unambiguous and easier on a human.  The trade-off is more complexity
in parsers and emitters.

Here's an example document, configuration for some hypothetical app::

    database:
        username: admin
        password: foobar  # TODO get prod passwords out of config
        socket: /var/tmp/database.sock
        options: {use_utf8: true}
    memcached:
        host: 10.0.0.99
    workers:
      - host: 10.0.0.101
        port: 2301
      - host: 10.0.0.102
        port: 2302

YAML often has more than one way to express the same data, leaving a human free
to use whichever is most convenient.  More convenient syntax tends to be more
contextual or whitespace-sensitive.  In the above document, you can see that
indenting is enough to make a nested mapping.  Integers and booleans are
automatically distinguished from unquoted strings, as well.


General syntax
--------------

As of 1.2, YAML is a strict superset of JSON.  Any valid JSON can be parsed in
the same structure with a YAML 1.2 parser.

YAML is designed around Unicode, not bytes, and its syntax assumes Unicode
input.  There is no syntactic mechanism for giving a character encoding; the
parser is expected to recognize BOMs for UTF-8, UTF-16, and UTF-32, but
otherwise a byte stream is assumed to be UTF-8.

The only vertical whitespace characters are U+000A LINE FEED and U+000D
CARRIAGE RETURN.  The only horizontal whitespace characters are U+0009 TAB and
U+0020 SPACE.  Other control characters are not allowed anywhere.  Otherwise,
anything goes.

YAML operates on *streams*, which can contain multiple distinct structures,
each parsed individually.  Each structure is called a *document*.

A document begins with ``---`` and ends with ``...``.  Both are optional,
though a ``...`` can only be followed by directives or ``---``.  You don't see
multiple documents very often, but it's a very useful feature for sending
intermittent chunks of data over a single network connection.  With JSON you'd
usually put each chunk on its own line and delimit with newlines; YAML has
support built in.

Documents may be preceded by *directives*, in which case the ``---`` is
required to indicate the end of the directives.  Directives are a ``%``
followed by an identifier and some parameters.  (This is how directives are
distinguished from a bare document without ``---``, so the first non-blank
non-comment line of a document can't start with a ``%``.)

There are only two directives at the moment: ``%YAML`` specifies the YAML
version of the document, and ``%TAG`` is used for tag shorthand, described
shortly.  Use of directives is, again, fairly uncommon.

*Comments* may appear anywhere.  ``#`` begins a comment, and it runs until the
end of the line.  In most cases, comments are whitespace: they don't affect
indentation level, they can appear between any two tokens, and a comment on its
own line is the same as a blank line.  The few exceptions are not too
surprising; for example, you can't have a comment between the key and colon in
``key:``.

A YAML document is a graph of values, called *nodes*, which come in three
general *kinds*: mappings, sequences, and scalars.  Each is described in detail
in its own section below.

Nodes may be prefixed with up to two properties: a *tag* and an *anchor*.
Order doesn't matter, and both are optional.

Tags
....

Tags are indicated with ``!``, and describe the *type* of a node.  This allows
for adding new types without changing the syntax or mingling types with data.
Tag names are limited to the URI character set, with any other characters
encoded as UTF-8 and then percent-encoded.

Tags are generally written as ``!foo!bar``, where ``!foo!`` is a *named tag
handle* that expands to a given prefix, kind of like XML namespacing.  Tag
handles must be defined by a ``%TAG`` directive at the beginning of the
stream::

    %TAG !foo! tag:example.com,2015:app/

The full name of ``!foo!bar`` would then be ``tag:example.com,2015:app/bar``.
YAML suggests that all full tag names begin with ``tag:`` and include a domain
so that they're globally unique.  That said, I have never in my life seen
anyone actually make use of this.

Instead, what everyone tends to do is make heavy use of the two special tag
handles:

* ``!bar`` uses the *primary tag handle* ``!``, which by default expands to
  ``!``.  So ``!bar`` just resolves to ``!bar``, a *local tag*, specific to
  the document and not expected to be globally unique.

  Note that *any* full tag name beginning with ``!`` is a local tag, so
  you're free to do something like this::

    %TAG !foo! !foo-types/

  Now ``!foo!bar`` is shorthand for ``!foo-types/bar``, which is still local.
  This is a little confusing, I know.
  
* ``!!bar`` uses the *secondary tag handle* ``!!``, which by default expands to
  ``tag:yaml.org,2002:``.  That's the prefix YAML uses for its own built-in
  types.  Unfortunately, PyYAML also uses it for Python-specific types, e.g.
  ``!!python/tuple``, and Camel has inherited this impolite behavior.

Both special handles can be reassigned with a ``%TAG`` directive, just like any
other handle.

Tags can also be written as ``!<foo>``, in which case ``foo`` is taken to be
the *verbatim* final name of the tag, ignoring ``%TAG`` and any other
resolution mechanism.

Every node has a tag, whether it's given one explicitly or not.  Nodes without
explicit tags are given one of two special *non-specific* tags: ``!`` for
quoted and folded scalars; or ``?`` for sequences, mappings, and plain scalars.

The ``?`` tag tells the application to do *tag resolution*.  Technically, this
means the application can do any kind of arbitrary inspection to figure out the
type of the node.  In practice, it just means that scalars are inspected to see
whether they're booleans, integers, floats, whatever else, or just strings.

The ``!`` tag forces a node to be interpreted as a basic built-in type, based
on its kind: ``!!str``, ``!!seq``, or ``!map``.  You can explicitly give the
``!`` tag to a node if you want, for example writing ``! true`` or ``! 133`` to
force parsing as strings.  Or you could use quotes.  Just saying.

Anchors
.......

The other node property is the *anchor*, which is how YAML can store recursive
data structures.  Anchor names are prefixed with ``&`` and can't contain
whitespace, brackets, braces, or commas.

An *alias node* is an anchor name prefixed with ``*``, and indicates that the
node with that anchor name should occur in both places.  For example, you could
share configuration::

    host1:
        &common-host
        os: linux
        arch: x86_64
    host2: *common-host

Or serialize a list that contains itself::

    &me [*me]

This is **not** a copy.  The exact same value is reused.

An alias node refers to the most recent anchor with the same name.  Anchor
names can be reassigned, and must appear before any alias node that tries to
refer to them.

Anchor names aren't intended to carry information, which unfortunately means
that most YAML parsers throw them away, and re-serializing a document will get
you anchor names like ``ANCHOR1``.


Kinds of value
--------------

As mentioned above, there are three kinds, which reflect the general shape of
some data.  Scalars are individual values; sequences are ordered collections;
mappings are unordered associations.  Each can be written in either a
whitespace-sensitive *block style* or a more compact and explicit *flow style*.

Scalars
.......

Most values in a YAML document will be *plain scalars*.  They're defined by
exclusion: if it's not anything else, it's a plain scalar.  Technically, they
can only be flow style, so they're really "plain flow scalar style" scalars.

Plain scalars are the most flexible kind of value, and may resolve to a variety
of types:

* Integers become, well, integers (``!!int``).  Leading ``0``, ``0b``, and
  ``0x`` are recognized as octal, binary, and hexadecimal.  ``_`` is allowed,
  and ignored.  Curiously, ``:`` is allowed and treated as a base 60 delimiter,
  so you can write a time as ``1:59`` and it'll be loaded as the number of
  seconds, 119.

* Floats become floats (``!!float``).  Scientific notation using ``e`` is also
  recognized.  As with integers, ``_`` is ignored and ``:`` indicates base 60,
  though only the last component can have a fractional part.  Positive
  infinity, negative infinity, and not-a-number are recognized with a leading
  dot: ``.inf``, ``-.inf``, and ``.nan``.

* ``true`` and ``false`` become booleans (``!!bool``).  ``y``, ``n``, ``yes``, ``no``,
  ``on``, and ``off`` are allowed as synonyms.  Uppercase and title case are
  also recognized.

* ``~`` and ``null`` become nulls (``!!null``), which is ``None`` in Python.  A
  completely empty value also becomes null.

* ISO8601 dates are recognized (``!!timestamp``), with whitespace allowed
  between the date and time.  The time is also optional, and defaults to
  midnight UTC.

* ``=`` is a special value (``!!value``) used as a key in mappings.  I've never
  seen it actually used, the thing it does is nonsense in Python, and PyYAML
  doesn't support it correctly anyway, so don't worry about it.  Just remember
  you can't use ``=`` as a plain string.

* ``<<`` is another special value (``!!merge``) used as a key in mappings.
  This one is actually kind of useful; it's described below.

Otherwise, it's a string.  Well.  Probably.  As part of tag resolution, an
application is allowed to parse plain scalars however it wants; you might add
logic that parses ``1..5`` as a range type, or you might recognize keywords and
replace them with special objects.  (This is what PyYAML's
``add_implicit_resolver`` is for.)  But if you're doing any of that, you're
hopefully aware of it.

Between the above parsing and conflicts with the rest of YAML's syntax, for a
plain scalar to be a string, it must meet these restrictions:

* It must not be ``true``, ``false``, ``yes``, ``no``, ``y``, ``n``, ``on``,
  ``off``, ``null``, or any of those words in uppercase or title case, which
  would all be parsed as booleans or nulls.

* It must not be ``~``, ``=``, or ``<<``, which are all special values.

* It must not be something that looks like a number or timestamp.  I wouldn't
  bet on anything that consists exclusively of digits, dashes, underscores, and
  colons.

* The first character must not be any of: ``[`` ``]`` ``{`` ``}`` ``,`` ``#``
  ``&`` ``*`` ``!`` ``|`` ``>`` ``'`` ``"`` ``%`` ``@`` `````.  All of these
  are YAML syntax for some other kind of construct.

* If the first character is ``?``, ``:``, or ``-``, the next character must not
  be whitespace.  Otherwise it'll be parsed as a block mapping or sequence.

* It must not contain `` #`` or ``: ``, which would be parsed as a comment or a
  key.  A hash not preceded by space or a colon not followed by space is fine.

* If the string is inside a flow collection (i.e., inside ``[...]`` or
  ``{...}``), it must not contain any of ``[`` ``]`` ``{`` ``}`` ``,``, which
  would all be parsed as part of the collection syntax.

* Leading and trailing whitespace are ignored.

* If the string is broken across lines, then the newline and any adjacent
  whitespace are collapsed into a single space.

That actually leaves you fairly wide open; the biggest restriction is on the
first character.  You can have spaces, you can wrap across lines, you can
include whatever (non-control) Unicode you want.

If you need explicit strings, you have some other options.


Strings
.......

YAML has lots of ways to write explicit strings.  Aside from plain scalars,
there are two other *flow scalar styles*.

Single-quoted strings are surrounded by ``'``.  Single quotes may be escaped as
``''``, but otherwise no escaping is done at all.  You may wrap over multiple
lines, but the newline and any surrounding whitespace becomes a single space.
A line containing only whitespace becomes a newline.

Double-quoted strings are surrounded by ``"``.  Backslash escapes are recognized:

==============      ======
Sequence            Result
==============      ======
``\0``              U+0000 NUL
``\a``              U+0007 ALARM
``\b``              U+0008 BACKSPACE
``\t``              U+0009 TAB
``\n``              U+000A LINE FEED
``\v``              U+000B VERTICAL TAB
``\f``              U+000C FORM FEED
``\r``              U+000D CARRIAGE RETURN
``\e``              U+001B ESCAPE
``\"``              U+0022 DOUBLE QUOTE
``\/``              U+002F SLASH
``\\``              U+005C BACKSLASH
``\N``              U+0085
``\_``              U+00A0 NON-BREAKING SPACE
``\L``              U+2028 LINE SEPARATOR
``\P``              U+2029 PARAGRAPH SEPARATOR
``\xNN``            Unicode character ``NN``
``\uNNNN``          Unicode character ``NNNN``
``\UNNNNNNNN``      Unicode character ``NNNNNNNN``
==============      ======

As usual, you may wrap a double-quoted string across multiple lines, but the
newline and any surrounding whitespace becomes a single space.  As with
single-quoted strings, a line containing only whitespace becomes a newline.
You can escape spaces and tabs to protect them from being thrown away.  You
can also escape a newline to preserve any trailing whitespace on that line, but
throw away the newline and any leading whitespace on the next line.

These rules are weird, so here's a contrived example::

    "line  \
        one

        line two\n\
    \ \ line three\nline four\n
    line five
    "

Which becomes::

    line  one
    line two
      line three
    line four
     line five 

Right, well, I hope that clears that up.

There are also two *block scalar styles*, both consisting of a header followed by an
indented block.  The header is usually just a single character, indicating
which block style to use.

``|`` indicates *literal style*, which preserves all newlines in the indented
block.  ``>`` indicates *folded style*, which performs the same line folding as
with quoted strings.  Escaped characters are not recognized in either style.
Indentation, the initial newline, and any leading blank lines are always
ignored.

So to represent this string::

    This is paragraph one.

    This is paragraph two.

You could use either literal style::

    |
        This is paragraph one.

        This is paragraph two.

Or folded style::

    >
        This is
        paragraph one.


        This
        is paragraph
        two.

Obviously folded style is more useful if you have paragraphs with longer lines.

The header has some other features, but I've never seen them used.  It consists
of up to three parts.

1. The character indicating which block style to use.
2. Optionally, the indentation level of the indented block, relative to its
   parent.  You only need this if the first line of the block starts with a
   space; otherwise the space will count as part of the indentation.
3. Optionally, a "chomping" indicator.  The default behavior is to include the
   final newline as part of the string, but ignore any subsequent empty lines.
   You can use ``-`` here to ignore the final newline as well, or use ``+`` to
   preserve all trailing whitespace verbatim.

You can put a comment on the same line as the header, but a comment on the next
line would be interpreted as part of the indented block.  You can also put a
tag or an anchor before the header, as with any other node.


Sequences
---------

Sequences are ordered collections, with type ``!!seq``.  They're pretty simple.

Flow style is a comma-delimited list in square brackets, just like JSON:
``[one, two, 3]``.  A trailing comma is allowed, and whitespace is generally
ignored.  The contents must also be written in flow style.

Block style is written like a bulleted list::

    - one
    - two
    - 3
    - a plain scalar that's
      wrapped across multiple lines

Indentation determines where each element ends, and where the entire sequence
ends.

Other blocks may be nested without intervening newlines::

    - - one one
      - one two
    - - two one
      - two two


Mappings
--------

Mappings are unordered, er, mappings, with type ``!!map``.  The keys must be
unique, but may be of any type.  Also, they're unordered.

Did I mention that mappings are **unordered**?  The order of the keys in the
document is irrelevant and arbitrary.  If you need order, you need a sequence.

Flow style looks unsurprisingly like JSON: ``{x: 1, y: 2}``.  Again, a trailing
comma is allowed, and whitespace doesn't matter.

As a special case, inside a sequence, you can write a single-pair mapping
without the braces.  So ``[a: b, c: d, e: f]`` is a sequence containing three
mappings.  This is allowed in block sequences too, and is used for ``!!omap``.

Block style is actually a little funny.  The canonical form is a little
surprising::

    ? x
    : 1
    ? y
    : 2

``?`` introduces a key, and ``:`` introduces a value.  You very rarely see this
form, because the ``?`` is optional as long as the key and colon are all on one
line (to avoid ambiguity) and the key is no more than 1024 characters long (to
avoid needing infinite lookahead).

So that's more commonly written like this::

    x: 1
    y: 2

The explicit ``?`` syntax is more useful for complex keys.  For example, it's
the only way to use block styles in the key::

    ? >
        If a train leaves Denver at 5:00 PM traveling at 90 MPH, and another
        train leaves New York City at 10:00 PM traveling at 80 MPH, by how many
        minutes are you going to miss your connection?
    : Depends whether we're on Daylight Saving Time or not.

Other than the syntactic restrictions, an implicit key isn't special in any way
and can also be of any type::

    true: false
    null: null
    up: down
    [0, 1]: [1, 0]

It's fairly uncommon to see anything but strings as keys, though, since
languages often don't support it.  Python can't have lists and dicts as dict
keys; Perl 5 and JavaScript only support string keys; and so on.

Unlike sequences, you may **not** nest another block inside a block mapping on
the same line.  This is invalid::

    one: two: buckle my shoe

But this is fine::

    - one: 1
      two: 2
    - three: 3
      four: 4

You can also nest a block sequence without indenting::

    foods:
    - burger
    - fries
    drinks:
    - soda
    - iced tea

One slight syntactic wrinkle: in either style, the colon must be followed by
whitespace.  ``foo:bar`` is a single string, remember.  (For JSON's sake, the
whitespace can be omitted if the colon immediately follows a flow sequence, a
flow mapping, or a quoted string.)

Merge keys
..........

These are written ``<<`` and have type ``!!merge``.  A merge key should have
another mapping (or sequence of mappings) as its value.  Each mapping is merged
into the containing mapping, with any existing keys left alone.  The actual
``<<`` key is never shown to the application.

This is generally used in conjunction with anchors to share default values::

    defaults: &DEFAULTS
        use-tls: true
        verify-host: true
    host1:
        <<: *DEFAULTS
        hostname: example.com
    host2:
        <<: *DEFAULTS
        hostname: example2.com
    host3:
        <<: *DEFAULTS
        hostname: example3.com
        # we have a really, really good reason for doing this, really
        verify-host: false
