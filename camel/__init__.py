try:
    from yaml import CSafeDumper as SafeDumper
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeDumper
    from yaml import SafeLoader


class ScopedDumper(SafeDumper):
    """Subclass of yaml's `SafeDumper` that scopes representers to the
    instance, rather than to the particular class, because damn.
    """
    def __init__(self, *args, **kwargs):
        super(ScopedDumper, self).__init__(*args, **kwargs)
        self.yaml_representers = SafeDumper.yaml_representers.copy()
        self.yaml_multi_representers = SafeDumper.yaml_multi_representers.copy()

    def add_representer(self, data_type, representer):
        self.yaml_representers[data_type] = representer

    def add_multi_representer(self, data_type, representer):
        self.yaml_multi_representers[data_type] = representer


class ScopedLoader(SafeLoader):
    """Subclass of yaml's `SafeLoader` that scopes constructors to the
    instance, rather than to the particular class, because damn.
    """
    def __init__(self, *args, **kwargs):
        super(ScopedLoader, self).__init__(*args, **kwargs)
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


YAML_TAG_PREFIX = 'tag:yaml.org,2002:'


def dump_ordered_dict(dumper, data):
    pairs = []
    for key, value in data.items():
        key_node = dumper.represent_data(key)
        value_node = dumper.represent_data(value)
        pairs.append((key_node, value_node))
    import yaml
    return yaml.MappingNode(YAML_TAG_PREFIX + 'omap', pairs, flow_style=False)


def camel_dump(obj):
    from collections import OrderedDict
    from io import StringIO
    out = StringIO()
    dumper = ScopedDumper(out)
    dumper.add_representer(OrderedDict, dump_ordered_dict)
    dumper.open()
    dumper.represent(obj)
    dumper.close()
    return out.getvalue()


if __name__ == '__main__':
    from collections import OrderedDict
    print(camel_dump(OrderedDict([('a', 1), ('b', 2), ('c', 3)])))
    print(camel_dump((1, 2, 3)))
