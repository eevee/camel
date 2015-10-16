# TODO, this specifically:
# - allow prefixing (in the Camel obj?) otherwise assume local, don't require the leading !
# - figure out namespacing and urls and whatever the christ
# - how do we actually store versions??  extra slash part??  maybe that works  (but then, forbid a type name that ends in such a slash part)
# - blacklist all the types in the yaml repo
# - document exactly which ones we support (i.e., yaml supports)
# TODO, general:
# - by default on python 2, assume everything is unicode unless it contains control characters?
# - DWIM -- block style except for very short sequences (if at all?), quotey style for long text...

# TODO BEFORE PUBLISHING:
# - /must/ strip the leading ! from tag names and allow giving a prefix (difficulty: have to do %TAG directive manually)
# - /must/ remove loader and dumper arguments, no need for them!
# - /must/ remove type arg from loader  (would be nice to have as documentation, but is useless?  blurgh)
# - /must/ figure out what happens with subclasses, and block if necessary for now, or make opt-in (but then, what happens with the tag, to indicate the subclass?)
# - /must/ work on python 2
# - /must/ use python 3 semantics for strings
# - use # to delimit version, per spec suggestion
# - better versioning story, interop with no version somehow, what is the use case for versionless?  assuming it will never change?  imo should require version
# - should write some docs, both on camel and on yaml

# TODO test a versioned thing
# TODO how does versioning interact with unversioned...?  maybe /require/ version, don't default to None


# TODO from alex gaynor's talk, starting around 24m in:
# - class is deleted (if it's useless, just return a dummy value)
# - attribute changes

# TODO minor questions and gripes:
# - should this complain if there are overlapping definitions?
# - Camel.load() should balk if there's != 1 object
# - need a Camel.load_all() (which can iterate)
# - how do we handle subclasses?  how does yaml?  what if there are conflicts?
# - dumper and loader could be easily made to work on methods...  i think...  in py3


import collections
import functools
from io import StringIO
import types

import yaml

try:
    from yaml import CSafeDumper as SafeDumper
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeDumper
    from yaml import SafeLoader


YAML_TAG_PREFIX = 'tag:yaml.org,2002:'


class CamelDumper(SafeDumper):
    """Subclass of yaml's `SafeDumper` that scopes representers to the
    instance, rather than to the particular class, because damn.
    """
    def __init__(self, *args, **kwargs):
        super(CamelDumper, self).__init__(*args, **kwargs)
        self.yaml_representers = SafeDumper.yaml_representers.copy()
        self.yaml_multi_representers = SafeDumper.yaml_multi_representers.copy()

    def add_representer(self, data_type, representer):
        self.yaml_representers[data_type] = representer

    def add_multi_representer(self, data_type, representer):
        self.yaml_multi_representers[data_type] = representer


class CamelLoader(SafeLoader):
    """Subclass of yaml's `SafeLoader` that scopes constructors to the
    instance, rather than to the particular class, because damn.
    """
    def __init__(self, *args, **kwargs):
        super(CamelLoader, self).__init__(*args, **kwargs)
        self.yaml_constructors = SafeLoader.yaml_constructors.copy()
        self.yaml_multi_constructors = SafeLoader.yaml_multi_constructors.copy()
        self.yaml_implicit_resolvers = SafeLoader.yaml_implicit_resolvers.copy()

    def add_constructor(self, data_type, constructor):
        self.yaml_constructors[data_type] = constructor

    def add_multi_constructor(self, data_type, constructor):
        self.yaml_multi_constructors[data_type] = constructor

    def add_implicit_resolver(self, tag, regexp, first):
        if first is None:
            first = [None]
        for ch in first:
            self.yaml_implicit_resolvers.setdefault(ch, []).append((tag, regexp))

    def add_path_resolver(self, *args, **kwargs):
        # This API is non-trivial and claims to be experimental and unstable
        raise NotImplementedError


class Camel(object):
    def __init__(self, registries=()):
        self.registries = (STANDARD_TYPES,) + tuple(registries)

    def make_dumper(self, stream):
        dumper = CamelDumper(stream, default_flow_style=False)
        for registry in self.registries:
            registry.inject_dumpers(dumper)
        return dumper

    def dump(self, data):
        stream = StringIO()
        dumper = self.make_dumper(stream)
        dumper.open()
        dumper.represent(data)
        dumper.close()
        return stream.getvalue()

    def make_loader(self, stream):
        dumper = CamelLoader(stream)
        for registry in self.registries:
            registry.inject_loaders(dumper)
        return dumper

    def load(self, data):
        stream = StringIO(data)
        loader = self.make_loader(stream)
        return loader.get_data()


class CamelRegistry(object):
    frozen = False

    def __init__(self):
        self.dumpers = {}
        self.loaders = {}

    def freeze(self):
        self.frozen = True

    # Dumping

    def dumper(self, cls, tag, version=None):
        if self.frozen:
            raise RuntimeError("Can't add to a frozen registry")

        assert '@' not in tag
        if version is not None:
            assert isinstance(version, (int, float))
            tag = "{}@{}".format(tag, version)

        def decorator(f):
            self.dumpers[tag] = cls, functools.partial(self.run_representer, f, tag)
            return f

        return decorator

    def run_representer(self, representer, tag, dumper, data):
        canon_value = representer(dumper, data)
        # Note that we /do not/ support subclasses of the built-in types here,
        # to avoid complications from returning types that have their own
        # custom representers
        canon_type = type(canon_value)
        # TODO this gives no control over flow_style, style, and implicit.  do
        # we intend to figure it out ourselves?
        if canon_type in (dict, collections.OrderedDict):
            return dumper.represent_mapping(tag, canon_value, flow_style=False)
        elif canon_type in (tuple, list):
            return dumper.represent_sequence(tag, canon_value, flow_style=False)
        # TODO py2 compat?  long, something about str/unicode?
        elif canon_type in (int, float, bool, str, type(None)):
            return dumper.represent_scalar(tag, canon_value)
        else:
            raise TypeError(
                "Representers must return native YAML types, but the representer "
                "for {!r} returned {!r}, which is of type {!r}"
                .format(data, canon_value, canon_type))

    def inject_dumpers(self, dumper):
        for tag, (cls, representer) in self.dumpers.items():
            dumper.add_representer(cls, representer)

    # Loading
    # TODO implement "upgrader", which upgrades from one version to another

    def loader(self, cls, tag, version=None):
        if self.frozen:
            raise RuntimeError("Can't add to a frozen registry")

        # TODO is there any good point to passing in cls
        # TODO this is copy/pasted, and hokey besides
        assert '@' not in tag
        if version is not None:
            assert isinstance(version, (int, float))
            tag = "{}@{}".format(tag, version)

        def decorator(f):
            self.loaders[tag] = cls, functools.partial(self.run_constructor, f)
            return f

        return decorator

    def run_constructor(self, constructor, loader, node):
        if isinstance(node, yaml.ScalarNode):
            data = loader.construct_scalar(node)
        elif isinstance(node, yaml.SequenceNode):
            data = loader.construct_sequence(node, deep=True)
        elif isinstance(node, yaml.MappingNode):
            data = loader.construct_mapping(node, deep=True)
        else:
            raise TypeError("Not a primitive node: {!r}".format(node))
        return constructor(loader, data)

    def inject_loaders(self, loader):
        for tag, (cls, constructor) in self.loaders.items():
            loader.add_constructor(tag, constructor)


# TODO "raw" loaders and dumpers that get access to loader/dumper and deal with
# raw nodes?
# TODO multi_constructor, multi_representer, implicit_resolver


# YAML's "language-independent types" — not builtins, but supported with
# standard !! tags.  Most of them are built into pyyaml, but OrderedDict is
# curiously overlooked.  Loaded first by default into every Camel object.
# Ref: http://yaml.org/type/
# TODO by default, dump frozenset as though it were a set?  how
STANDARD_TYPES = CamelRegistry()

@STANDARD_TYPES.dumper(collections.OrderedDict, YAML_TAG_PREFIX + 'omap')
def _dump_ordered_dict(dumper, data):
    pairs = []
    for key, value in data.items():
        pairs.append({key: value})
    return pairs


@STANDARD_TYPES.loader(collections.OrderedDict, YAML_TAG_PREFIX + 'omap')
def _load_ordered_dict(loader, data):
    # TODO assert only single kv per thing
    return collections.OrderedDict(
        next(iter(datum.items())) for datum in data
    )

STANDARD_TYPES.freeze()


# TODO seems like we should always support /loading/ these python types...?
PYTHON_TYPES = CamelRegistry()


@PYTHON_TYPES.dumper(tuple, YAML_TAG_PREFIX + 'python/tuple')
def _dump_tuple(dumper, data):
    return list(data)


@PYTHON_TYPES.loader(tuple, YAML_TAG_PREFIX + 'python/tuple')
def _load_tuple(loader, data):
    return tuple(data)


@PYTHON_TYPES.dumper(complex, YAML_TAG_PREFIX + 'python/complex')
def _dump_complex(dumper, data):
    ret = repr(data)
    # Complex numbers become (1+2j), but the parens are superfluous
    if ret[0] == '(' and ret[-1] == ')':
        return ret[1:-1]
    else:
        return ret


@PYTHON_TYPES.loader(complex, YAML_TAG_PREFIX + 'python/complex')
def _load_complex(loader, data):
    return complex(data)


@PYTHON_TYPES.dumper(frozenset, YAML_TAG_PREFIX + 'python/frozenset')
def _dump_complex(dumper, data):
    try:
        return list(sorted(data))
    except TypeError:
        return list(data)


@PYTHON_TYPES.loader(frozenset, YAML_TAG_PREFIX + 'python/frozenset')
def _load_complex(loader, data):
    return frozenset(data)


if hasattr(types, 'SimpleNamespace'):
    @PYTHON_TYPES.dumper(types.SimpleNamespace, YAML_TAG_PREFIX + 'python/namespace')
    def _dump_simple_namespace(dumper, data):
        return data.__dict__


    @PYTHON_TYPES.loader(types.SimpleNamespace, YAML_TAG_PREFIX + 'python/namespace')
    def _load_simple_namespace(loader, data):
        return types.SimpleNamespace(**data)


PYTHON_TYPES.freeze()
