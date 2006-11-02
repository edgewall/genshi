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

import htmlentitydefs
import operator
import re

__all__ = ['Stream', 'Markup', 'escape', 'unescape', 'Namespace', 'QName']


class StreamEventKind(str):
    """A kind of event on an XML stream."""
    __slots__ = []
    _instances = {}

    def __new__(cls, val):
        return cls._instances.setdefault(val, str.__new__(cls, val))


class Stream(object):
    """Represents a stream of markup events.
    
    This class is basically an iterator over the events.
    
    Also provided are ways to serialize the stream to text. The `serialize()`
    method will return an iterator over generated strings, while `render()`
    returns the complete generated text at once. Both accept various parameters
    that impact the way the stream is serialized.
    
    Stream events are tuples of the form:

      (kind, data, position)

    where `kind` is the event kind (such as `START`, `END`, `TEXT`, etc), `data`
    depends on the kind of event, and `position` is a `(filename, line, offset)`
    tuple that contains the location of the original element or text in the
    input. If the original location is unknown, `position` is `(None, -1, -1)`.
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
        a stream is anything that iterators over events):
        
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


class Attrs(list):
    """Sequence type that stores the attributes of an element.
    
    The order of the attributes is preserved, while accessing and manipulating
    attributes by name is also supported.
    
    >>> attrs = Attrs([('href', '#'), ('title', 'Foo')])
    >>> attrs
    Attrs([(QName(u'href'), '#'), (QName(u'title'), 'Foo')])
    
    >>> 'href' in attrs
    True
    >>> 'tabindex' in attrs
    False
    
    >>> attrs.get(u'title')
    'Foo'
    >>> attrs.set(u'title', 'Bar')
    >>> attrs
    Attrs([(QName(u'href'), '#'), (QName(u'title'), 'Bar')])
    >>> attrs.remove(u'title')
    >>> attrs
    Attrs([(QName(u'href'), '#')])
    
    New attributes added using the `set()` method are appended to the end of
    the list:
    
    >>> attrs.set(u'accesskey', 'k')
    >>> attrs
    Attrs([(QName(u'href'), '#'), (QName(u'accesskey'), 'k')])
    
    An `Attrs` instance can also be initialized with keyword arguments.
    
    >>> attrs = Attrs(class_='bar', href='#', title='Foo')
    >>> attrs.get('class')
    'bar'
    >>> attrs.get('href')
    '#'
    >>> attrs.get('title')
    'Foo'
    
    Reserved words can be used by appending a trailing underscore to the name,
    and any other underscore is replaced by a dash:
    
    >>> attrs = Attrs(class_='bar', accept_charset='utf-8')
    >>> attrs.get('class')
    'bar'
    >>> attrs.get('accept-charset')
    'utf-8'
    
    Thus this shorthand can not be used if attribute names should contain
    actual underscore characters.
    """
    __slots__ = []

    def __init__(self, attrib=None, **kwargs):
        """Create the `Attrs` instance.
        
        If the `attrib` parameter is provided, it is expected to be a sequence
        of `(name, value)` tuples.
        """
        if attrib is None:
            attrib = []
        list.__init__(self, [(QName(name), value) for name, value in attrib])
        for name, value in kwargs.items():
            self.set(name.rstrip('_').replace('_', '-'), value)

    def __contains__(self, name):
        """Return whether the list includes an attribute with the specified
        name.
        """
        for attr, _ in self:
            if attr == name:
                return True

    def __repr__(self):
        if not self:
            return 'Attrs()'
        return 'Attrs(%s)' % list.__repr__(self)

    def get(self, name, default=None):
        """Return the value of the attribute with the specified name, or the
        value of the `default` parameter if no such attribute is found.
        """
        for attr, value in self:
            if attr == name:
                return value
        return default

    def remove(self, name):
        """Remove the attribute with the specified name.
        
        If no such attribute is found, this method does nothing.
        """
        for idx, (attr, _) in enumerate(self):
            if attr == name:
                del self[idx]
                break

    def set(self, name, value):
        """Set the specified attribute to the given value.
        
        If an attribute with the specified name is already in the list, the
        value of the existing entry is updated. Otherwise, a new attribute is
        appended to the end of the list.
        """
        for idx, (attr, _) in enumerate(self):
            if attr == name:
                self[idx] = (QName(attr), value)
                break
        else:
            self.append((QName(name), value))

    def totuple(self):
        """Return the attributes as a markup event.
        
        The returned event is a TEXT event, the data is the value of all
        attributes joined together.
        """
        return TEXT, u''.join([x[1] for x in self]), (None, -1, -1)


def plaintext(text, keeplinebreaks=True):
    """Returns the text as a `unicode` string with all entities and tags
    removed.
    """
    text = stripentities(striptags(text))
    if not keeplinebreaks:
        text = text.replace(u'\n', u' ')
    return text

def stripentities(text, keepxmlentities=False):
    """Return a copy of the given text with any character or numeric entities
    replaced by the equivalent UTF-8 characters.
    
    If the `keepxmlentities` parameter is provided and evaluates to `True`,
    the core XML entities (&amp;, &apos;, &gt;, &lt; and &quot;) are not
    stripped.
    """
    def _replace_entity(match):
        if match.group(1): # numeric entity
            ref = match.group(1)
            if ref.startswith('x'):
                ref = int(ref[1:], 16)
            else:
                ref = int(ref, 10)
            return unichr(ref)
        else: # character entity
            ref = match.group(2)
            if keepxmlentities and ref in ('amp', 'apos', 'gt', 'lt', 'quot'):
                return '&%s;' % ref
            try:
                codepoint = htmlentitydefs.name2codepoint[ref]
                return unichr(codepoint)
            except KeyError:
                if keepxmlentities:
                    return '&amp;%s;' % ref
                else:
                    return ref
    return re.sub(r'&(?:#((?:\d+)|(?:[xX][0-9a-fA-F]+));?|(\w+);)',
                  _replace_entity, text)

def striptags(text):
    """Return a copy of the text with all XML/HTML tags removed."""
    return re.sub(r'<[^>]*?>', '', text)


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
        return '<%s "%s">' % (self.__class__.__name__, self)

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
