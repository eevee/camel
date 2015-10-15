# TODO, this specifically:
# - figure out namespacing and urls and whatever the christ
# - how do we actually store versions??  extra slash part??  maybe that works  (but then, forbid a type name that ends in such a slash part)
# - blacklist all the types in the yaml repo
# - document exactly which ones we support (i.e., yaml supports)
# TODO, general:
# - by default on python 2, assume everything is unicode unless it contains control characters?
# - DWIM -- block style except for very short sequences (if at all?), quotey style for long text...

import collections
import functools
from io import StringIO

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
    def __init__(self, registries):
        self.registries = registries

    def make_dumper(self, stream):
        dumper = CamelDumper(stream, default_flow_style=False)
        for registry in self.registries:
            # TODO should this complain if there are overlapping definitions?
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
        # TODO what if there are multiple objects...?
        return loader.get_data()


class CamelRegistry(object):
    def __init__(self):
        self.dumpers = {}
        self.loaders = {}

    # TODO: how do we handle subclasses?  how does yaml?  what if there are conflicts?

    # Dumping

    def dumper(self, cls, tag, version=None):
        assert '/' not in tag
        if version is not None:
            assert isinstance(version, (int, float))
            tag = "{}/{}".format(tag, version)

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

    def loader(self, cls, tag, version=None):
        # TODO is there any good point to passing in cls
        # TODO this is copy/pasted, and hokey besides
        assert '/' not in tag
        if version is not None:
            assert isinstance(version, (int, float))
            tag = "{}/{}".format(tag, version)

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


python_registry = CamelRegistry()
# TODO tag tuples?  sets?  frozensets?  complex?  any other python types?
# TODO py3's types.SimpleNamespace
# TODO some kinda option, or a separate registry, for tagging python versus collapsing to yaml types?
# TODO "raw" loaders and dumpers that get access to loader/dumper and deal with raw nodes?
# TODO multi_constructor, multi_representer, implicit_resolver


@python_registry.dumper(collections.OrderedDict, YAML_TAG_PREFIX + 'omap')
def _dump_ordered_dict(dumper, data):
    pairs = []
    for key, value in data.items():
        pairs.append({key: value})
    return pairs


@python_registry.loader(collections.OrderedDict, YAML_TAG_PREFIX + 'omap')
def _load_ordered_dict(loader, data):
    # TODO assert only single kv per thing
    return collections.OrderedDict(
        next(iter(datum.items())) for datum in data
    )


# TODO versioned thing
# TODO how does it interact with unversioned...?  maybe require version
