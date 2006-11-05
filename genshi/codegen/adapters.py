"""a set of Inline adapters, which convert from inlined structures to Genshi core structures"""

from genshi.path import Path

def get_attrib(attrib, name, default=None):
    """return an 'attribute' name from a list of tuples, similar to genshi.core.Attrib"""
    for attr, value in attrib:
        if attr == name:
            return value
    return default

class InlineStream(object):
    """works similarly to genshi.core.Stream"""
    def __init__(self, generator, context):
        self.code = generator.code
        self.filters = generator.filters
        self.context = context
        self.stream = self.code.go(self.context)
    def __iter__(self):
        return list(self.stream)

    def __or__(self, function):
        return InlineStream(function(self))

    def filter(self, *filters):
        return reduce(operator.or_, (self,) + filters)

    def render(self, method='xml', encoding='utf-8', **kwargs):
        generator = self.serialize(method=method, **kwargs)
        output = u''.join(list(generator))
        if encoding is not None:
            errors = 'replace'
            if method != 'text':
                errors = 'xmlcharrefreplace'
            return output.encode(encoding, errors)
        return output

    def select(self, path, namespaces=None, variables=None):
        return InlinedPath(path).select(self, namespaces, variables)

    def serialize(self, method='xml', **kwargs):
        stream = self.stream
        for filter_ in self.filters:
            stream = filter_(stream)
        for evt in stream:
            yield evt[3]

    def __str__(self):
        return self.render()

    def __unicode__(self):
        return self.render(encoding=None)

class InlineQName(object):
    """creates a QName-like object from a START event"""
    def __init__(self, event):
        self.namespace = event[1][0]
        self.localname = event[1][1]
        
class InlinedPath(Path):
    """overrides Path.test to adapt incoming events from inlined to Genshi."""
    def test(self, ignore_context=False):
        t = super(InlinedPath, self).test(ignore_context=ignore_context)
        def _test(event, namespaces, variables, updateonly=False):
            if event[0] is START:
                return t((event[0], (InlineQName(event), event[1][1]), event[2]), namespaces, variables, updateonly=updateonly)
            else:
                return t(event[0:3], namespaces, variables, updateonly=updateonly)
        return _test
