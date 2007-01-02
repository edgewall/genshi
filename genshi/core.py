# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Core classes for markup processing."""

import operator

from genshi.util import plaintext, stripentities, striptags

__all__ = ['Stream', 'Markup', 'escape', 'unescape', 'Attrs', 'Namespace',
           'QName']


class StreamEventKind(str):
    """A kind of event on a markup stream."""
    __slots__ = []
    _instances = {}

    def __new__(cls, val):
        return cls._instances.setdefault(val, str.__new__(cls, val))


class Stream(object):
    """Represents a stream of markup events.
    
    This class is basically an iterator over the events.
    
    Stream events are tuples of the form:
    
      (kind, data, position)
    
    where `kind` is the event kind (such as `START`, `END`, `TEXT`, etc), `data`
    depends on the kind of event, and `position` is a `(filename, line, offset)`
    tuple that contains the location of the original element or text in the
    input. If the original location is unknown, `position` is `(None, -1, -1)`.
    
    Also provided are ways to serialize the stream to text. The `serialize()`
    method will return an iterator over generated strings, while `render()`
    returns the complete generated text at once. Both accept various parameters
    that impact the way the stream is serialized.
    """
    __slots__ = ['events']

    START = StreamEventKind('START') # a start tag
    END = StreamEventKind('END') # an end tag
    TEXT = StreamEventKind('TEXT') # literal text
    DOCTYPE = StreamEventKind('DOCTYPE') # doctype declaration
    START_NS = StreamEventKind('START_NS') # start namespace mapping
    END_NS = StreamEventKind('END_NS') # end namespace mapping
    START_CDATA = StreamEventKind('START_CDATA') # start CDATA section
    END_CDATA = StreamEventKind('END_CDATA') # end CDATA section
    PI = StreamEventKind('PI') # processing instruction
    COMMENT = StreamEventKind('COMMENT') # comment

    def __init__(self, events):
        """Initialize the stream with a sequence of markup events.
        
        @param events: a sequence or iterable providing the events
        """
        self.events = events

    def __iter__(self):
        return iter(self.events)

    def __or__(self, function):
        """Override the "bitwise or" operator to apply filters or serializers
        to the stream, providing a syntax similar to pipes on Unix shells.
        
        Assume the following stream produced by the `HTML` function:
        
        >>> from genshi.input import HTML
        >>> html = HTML('''<p onclick="alert('Whoa')">Hello, world!</p>''')
        >>> print html
        <p onclick="alert('Whoa')">Hello, world!</p>
        
        A filter such as the HTML sanitizer can be applied to that stream using
        the pipe notation as follows:
        
        >>> from genshi.filters import HTMLSanitizer
        >>> sanitizer = HTMLSanitizer()
        >>> print html | sanitizer
        <p>Hello, world!</p>
        
        Filters can be any function that accepts and produces a stream (where
        a stream is anything that iterates over events):
        
        >>> def uppercase(stream):
        ...     for kind, data, pos in stream:
        ...         if kind is TEXT:
        ...             data = data.upper()
        ...         yield kind, data, pos
        >>> print html | sanitizer | uppercase
        <p>HELLO, WORLD!</p>
        
        Serializers can also be used with this notation:
        
        >>> from genshi.output import TextSerializer
        >>> output = TextSerializer()
        >>> print html | sanitizer | uppercase | output
        HELLO, WORLD!
        
        Commonly, serializers should be used at the end of the "pipeline";
        using them somewhere in the middle may produce unexpected results.
        """
        return Stream(_ensure(function(self)))

    def filter(self, *filters):
        """Apply filters to the stream.
        
        This method returns a new stream with the given filters applied. The
        filters must be callables that accept the stream object as parameter,
        and return the filtered stream.
        
        The call:
        
            stream.filter(filter1, filter2)
        
        is equivalent to:
        
            stream | filter1 | filter2
        """
        return reduce(operator.or_, (self,) + filters)

    def render(self, method='xml', encoding='utf-8', **kwargs):
        """Return a string representation of the stream.
        
        @param method: determines how the stream is serialized; can be either
                       "xml", "xhtml", "html", "text", or a custom serializer
                       class
        @param encoding: how the output string should be encoded; if set to
                         `None`, this method returns a `unicode` object

        Any additional keyword arguments are passed to the serializer, and thus
        depend on the `method` parameter value.
        """
        generator = self.serialize(method=method, **kwargs)
        output = u''.join(list(generator))
        if encoding is not None:
            errors = 'replace'
            if method != 'text':
                errors = 'xmlcharrefreplace'
            return output.encode(encoding, errors)
        return output

    def select(self, path, namespaces=None, variables=None):
        """Return a new stream that contains the events matching the given
        XPath expression.
        
        @param path: a string containing the XPath expression
        """
        from genshi.path import Path
        return Path(path).select(self, namespaces, variables)

    def serialize(self, method='xml', **kwargs):
        """Generate strings corresponding to a specific serialization of the
        stream.
        
        Unlike the `render()` method, this method is a generator that returns
        the serialized output incrementally, as opposed to returning a single
        string.
        
        @param method: determines how the stream is serialized; can be either
                       "xml", "xhtml", "html", "text", or a custom serializer
                       class

        Any additional keyword arguments are passed to the serializer, and thus
        depend on the `method` parameter value.
        """
        from genshi import output
        cls = method
        if isinstance(method, basestring):
            cls = {'xml':   output.XMLSerializer,
                   'xhtml': output.XHTMLSerializer,
                   'html':  output.HTMLSerializer,
                   'text':  output.TextSerializer}[method]
        return cls(**kwargs)(_ensure(self))

    def __str__(self):
        return self.render()

    def __unicode__(self):
        return self.render(encoding=None)


START = Stream.START
END = Stream.END
TEXT = Stream.TEXT
DOCTYPE = Stream.DOCTYPE
START_NS = Stream.START_NS
END_NS = Stream.END_NS
START_CDATA = Stream.START_CDATA
END_CDATA = Stream.END_CDATA
PI = Stream.PI
COMMENT = Stream.COMMENT

def _ensure(stream):
    """Ensure that every item on the stream is actually a markup event."""
    for event in stream:
        if type(event) is not tuple:
            if hasattr(event, 'totuple'):
                event = event.totuple()
            else:
                event = TEXT, unicode(event), (None, -1, -1)
        yield event


class Attrs(tuple):
    """Immutable sequence type that stores the attributes of an element.
    
    Ordering of the attributes is preserved, while accessing by name is also
    supported.
    
    >>> attrs = Attrs([('href', '#'), ('title', 'Foo')])
    >>> attrs
    Attrs([(QName(u'href'), '#'), (QName(u'title'), 'Foo')])
    
    >>> 'href' in attrs
    True
    >>> 'tabindex' in attrs
    False
    >>> attrs.get(u'title')
    'Foo'
    
    Instances may not be manipulated directly. Instead, the operators `|` and
    `-` can be used to produce new instances that have specific attributes
    added, replaced or removed.
    
    To remove an attribute, use the `-` operator. The right hand side can be
    either a string or a set/sequence of strings, identifying the name(s) of
    the attribute(s) to remove:
    
    >>> attrs - 'title'
    Attrs([(QName(u'href'), '#')])
    >>> attrs - ('title', 'href')
    Attrs()
    
    The original instance is not modified, but the operator can of course be
    used with an assignment:

    >>> attrs
    Attrs([(QName(u'href'), '#'), (QName(u'title'), 'Foo')])
    >>> attrs -= 'title'
    >>> attrs
    Attrs([(QName(u'href'), '#')])
    
    To add a new attribute, use the `|` operator, where the right hand value
    is a sequence of `(name, value)` tuples (which includes `Attrs` instances):
    
    >>> attrs | [(u'title', 'Bar')]
    Attrs([(QName(u'href'), '#'), (QName(u'title'), 'Bar')])
    
    If the attributes already contain an attribute with a given name, the value
    of that attribute is replaced:
    
    >>> attrs | [(u'href', 'http://example.org/')]
    Attrs([(QName(u'href'), 'http://example.org/')])
    
    """
    __slots__ = []

    def __new__(cls, items=()):
        """Create the `Attrs` instance.
        
        If the `items` parameter is provided, it is expected to be a sequence
        of `(name, value)` tuples.
        """
        return tuple.__new__(cls, [(QName(name), val) for name, val in items])

    def __contains__(self, name):
        """Return whether the list includes an attribute with the specified
        name.
        """
        for attr, _ in self:
            if attr == name:
                return True

    def __getslice__(self, i, j):
        return Attrs(tuple.__getslice__(self, i, j))

    def __or__(self, attrs):
        """Return a new instance that contains the attributes in `attrs` in
        addition to any already existing attributes.
        """
        repl = dict([(an, av) for an, av in attrs if an in self])
        return Attrs([(sn, repl.get(sn, sv)) for sn, sv in self] +
                     [(an, av) for an, av in attrs if an not in self])

    def __repr__(self):
        if not self:
            return 'Attrs()'
        return 'Attrs([%s])' % ', '.join([repr(item) for item in self])

    def __sub__(self, names):
        """Return a new instance with all attributes with a name in `names` are
        removed.
        """
        if isinstance(names, basestring):
            names = (names,)
        return Attrs([(name, val) for name, val in self if name not in names])

    def get(self, name, default=None):
        """Return the value of the attribute with the specified name, or the
        value of the `default` parameter if no such attribute is found.
        """
        for attr, value in self:
            if attr == name:
                return value
        return default

    def totuple(self):
        """Return the attributes as a markup event.
        
        The returned event is a TEXT event, the data is the value of all
        attributes joined together.
        """
        return TEXT, u''.join([x[1] for x in self]), (None, -1, -1)


class Markup(unicode):
    """Marks a string as being safe for inclusion in HTML/XML output without
    needing to be escaped.
    """
    __slots__ = []

    def __new__(cls, text='', *args):
        if args:
            text %= tuple(map(escape, args))
        return unicode.__new__(cls, text)

    def __add__(self, other):
        return Markup(unicode(self) + unicode(escape(other)))

    def __radd__(self, other):
        return Markup(unicode(escape(other)) + unicode(self))

    def __mod__(self, args):
        if not isinstance(args, (list, tuple)):
            args = [args]
        return Markup(unicode.__mod__(self, tuple(map(escape, args))))

    def __mul__(self, num):
        return Markup(unicode(self) * num)

    def __rmul__(self, num):
        return Markup(num * unicode(self))

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, unicode(self))

    def join(self, seq, escape_quotes=True):
        return Markup(unicode(self).join([escape(item, quotes=escape_quotes)
                                          for item in seq]))

    def escape(cls, text, quotes=True):
        """Create a Markup instance from a string and escape special characters
        it may contain (<, >, & and \").
        
        If the `quotes` parameter is set to `False`, the \" character is left
        as is. Escaping quotes is generally only required for strings that are
        to be used in attribute values.
        """
        if not text:
            return cls()
        if type(text) is cls:
            return text
        text = unicode(text).replace('&', '&amp;') \
                            .replace('<', '&lt;') \
                            .replace('>', '&gt;')
        if quotes:
            text = text.replace('"', '&#34;')
        return cls(text)
    escape = classmethod(escape)

    def unescape(self):
        """Reverse-escapes &, <, > and \" and returns a `unicode` object."""
        if not self:
            return u''
        return unicode(self).replace('&#34;', '"') \
                            .replace('&gt;', '>') \
                            .replace('&lt;', '<') \
                            .replace('&amp;', '&')

    def stripentities(self, keepxmlentities=False):
        """Return a copy of the text with any character or numeric entities
        replaced by the equivalent UTF-8 characters.
        
        If the `keepxmlentities` parameter is provided and evaluates to `True`,
        the core XML entities (&amp;, &apos;, &gt;, &lt; and &quot;) are not
        stripped.
        """
        return Markup(stripentities(self, keepxmlentities=keepxmlentities))

    def striptags(self):
        """Return a copy of the text with all XML/HTML tags removed."""
        return Markup(striptags(self))


escape = Markup.escape

def unescape(text):
    """Reverse-escapes &, <, > and \" and returns a `unicode` object."""
    if not isinstance(text, Markup):
        return text
    return text.unescape()


class Namespace(object):
    """Utility class creating and testing elements with a namespace.
    
    Internally, namespace URIs are encoded in the `QName` of any element or
    attribute, the namespace URI being enclosed in curly braces. This class
    helps create and test these strings.
    
    A `Namespace` object is instantiated with the namespace URI.
    
    >>> html = Namespace('http://www.w3.org/1999/xhtml')
    >>> html
    <Namespace "http://www.w3.org/1999/xhtml">
    >>> html.uri
    u'http://www.w3.org/1999/xhtml'
    
    The `Namespace` object can than be used to generate `QName` objects with
    that namespace:
    
    >>> html.body
    QName(u'http://www.w3.org/1999/xhtml}body')
    >>> html.body.localname
    u'body'
    >>> html.body.namespace
    u'http://www.w3.org/1999/xhtml'
    
    The same works using item access notation, which is useful for element or
    attribute names that are not valid Python identifiers:
    
    >>> html['body']
    QName(u'http://www.w3.org/1999/xhtml}body')
    
    A `Namespace` object can also be used to test whether a specific `QName`
    belongs to that namespace using the `in` operator:
    
    >>> qname = html.body
    >>> qname in html
    True
    >>> qname in Namespace('http://www.w3.org/2002/06/xhtml2')
    False
    """
    def __new__(cls, uri):
        if type(uri) is cls:
            return uri
        return object.__new__(cls, uri)

    def __getnewargs__(self):
        return (self.uri,)

    def __getstate__(self):
        return self.uri

    def __setstate__(self, uri):
        self.uri = uri

    def __init__(self, uri):
        self.uri = unicode(uri)

    def __contains__(self, qname):
        return qname.namespace == self.uri

    def __ne__(self, other):
        return not self == other

    def __eq__(self, other):
        if isinstance(other, Namespace):
            return self.uri == other.uri
        return self.uri == other

    def __getitem__(self, name):
        return QName(self.uri + u'}' + name)
    __getattr__ = __getitem__

    def __repr__(self):
        return '<Namespace "%s">' % self.uri

    def __str__(self):
        return self.uri.encode('utf-8')

    def __unicode__(self):
        return self.uri


# The namespace used by attributes such as xml:lang and xml:space
XML_NAMESPACE = Namespace('http://www.w3.org/XML/1998/namespace')


class QName(unicode):
    """A qualified element or attribute name.
    
    The unicode value of instances of this class contains the qualified name of
    the element or attribute, in the form `{namespace}localname`. The namespace
    URI can be obtained through the additional `namespace` attribute, while the
    local name can be accessed through the `localname` attribute.
    
    >>> qname = QName('foo')
    >>> qname
    QName(u'foo')
    >>> qname.localname
    u'foo'
    >>> qname.namespace
    
    >>> qname = QName('http://www.w3.org/1999/xhtml}body')
    >>> qname
    QName(u'http://www.w3.org/1999/xhtml}body')
    >>> qname.localname
    u'body'
    >>> qname.namespace
    u'http://www.w3.org/1999/xhtml'
    """
    __slots__ = ['namespace', 'localname']

    def __new__(cls, qname):
        if type(qname) is cls:
            return qname

        parts = qname.split(u'}', 1)
        if len(parts) > 1:
            self = unicode.__new__(cls, u'{%s' % qname)
            self.namespace, self.localname = map(unicode, parts)
        else:
            self = unicode.__new__(cls, qname)
            self.namespace, self.localname = None, unicode(qname)
        return self

    def __getnewargs__(self):
        return (self.lstrip('{'),)

    def __repr__(self):
        return 'QName(%s)' % unicode.__repr__(self.lstrip('{'))
