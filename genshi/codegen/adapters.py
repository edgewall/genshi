"""a set of Inline adapters, which convert from inlined structures to Genshi core structures"""

from genshi.path import Path
from genshi.core import Attrs
from genshi import template

def get_attrib(attrib, name, default=None):
    """return an 'attribute' name from a list of tuples, similar to genshi.core.Attrib"""
    for attr, value in attrib:
        if attr == name:
            return value
    return default

class InlineStream(object):
    def __init__(self, stream):
        self.stream = stream
    def __iter__(self):
        return iter(self.stream)

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
        return InlinePath(path).select(self, namespaces, variables)

    def serialize(self, method='xml', **kwargs):
        for evt in self.stream:
            yield evt[3]

    def __str__(self):
        return self.render()

    def __unicode__(self):
        return self.render(encoding=None)

class InlineEvent(object):
    __eventtypes__ = {}
    def __new__(cls, event):
        return object.__new__(InlineEvent.__eventtypes__.get(event[0], InlineEvent), event)
    def __init__(self, event):
        self.event = event
    def to_genshi(self):
        return self.event[0:3]

class InlineStartEvent(InlineEvent):
    def to_genshi(self):
        return (self.event[0], (InlineQName(self.event), Attrs(self.event[1][2])), self.event[2])
InlineEvent.__eventtypes__[template.START] = InlineStartEvent
        
class InlineQName(unicode):
    """creates a QName-like object from a START event"""
    def __new__(cls, event):
        self = unicode.__new__(cls, u'{%s}%s' % (event[1][0], event[1][1]))
        self.namespace = event[1][0]
        self.localname = event[1][1]
        return self
        
class InlinePath(Path):
    """overrides Path.test to adapt incoming events from inlined to Genshi."""
    def test(self, ignore_context=False):
        t = super(InlinePath, self).test(ignore_context=ignore_context)
        def _test(event, namespaces, variables, updateonly=False):
            return t(InlineEvent(event).to_genshi(), namespaces, variables, updateonly=updateonly)
        return _test
    def select(self, stream, namespaces=None, variables=None):
        if namespaces is None:
            namespaces = {}
        if variables is None:
            variables = {}
        stream = iter(stream)
        def _generate():
            test = self.test()
            for event in stream:
                result = test(event, namespaces, variables)
                if result is True:
                    yield event
                    depth = 1
                    while depth > 0:
                        subevent = stream.next()
                        if subevent[0] is template.START:
                            depth += 1
                        elif subevent[0] is template.END:
                            depth -= 1
                        yield subevent
                        test(subevent, namespaces, variables, updateonly=True)
                # assume 3-tupled return events are just the event that was tested.
                # TODO: Path tests will no longer return these ?
                elif isinstance(result, tuple):
                    yield event
                elif result:
                    # in genshi.path.Path, this could be an Attrs or a 3-tupled event.
                    # here, we only want Attrs to come out.
                    yield result
        return InlineStream(_generate())

    def __repr__(self):
        return "InlinePath(%s, %s, %s)" % (repr(self.source), repr(self.filename), repr(self.lineno))
        
        