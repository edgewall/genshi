# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.

"""Core classes for markup processing."""

import htmlentitydefs
import re
from StringIO import StringIO

__all__ = ['Stream', 'Markup', 'escape', 'unescape', 'Namespace', 'QName']


class StreamEventKind(str):
    """A kind of event on an XML stream."""


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
    depends on the kind of event, and `position` is a `(line, offset)` tuple
    that contains the location of the original element or text in the input.
    """
    __slots__ = ['events']

    START = StreamEventKind('START') # a start tag
    END = StreamEventKind('END') # an end tag
    TEXT = StreamEventKind('TEXT') # literal text
    PROLOG = StreamEventKind('PROLOG') # XML prolog
    DOCTYPE = StreamEventKind('DOCTYPE') # doctype declaration
    START_NS = StreamEventKind('START-NS') # start namespace mapping
    END_NS = StreamEventKind('END-NS') # end namespace mapping
    PI = StreamEventKind('PI') # processing instruction
    COMMENT = StreamEventKind('COMMENT') # comment

    def __init__(self, events):
        """Initialize the stream with a sequence of markup events.
        
        @oaram events: a sequence or iterable providing the events
        """
        self.events = events

    def __iter__(self):
        return iter(self.events)

    def render(self, method='xml', encoding='utf-8', filters=None, **kwargs):
        """Return a string representation of the stream.
        
        @param method: determines how the stream is serialized; can be either
                       'xml' or 'html', or a custom `Serializer` subclass
        @param encoding: how the output string should be encoded; if set to
                         `None`, this method returns a `unicode` object

        Any additional keyword arguments are passed to the serializer, and thus
        depend on the `method` parameter value.
        """
        generator = self.serialize(method=method, filters=filters, **kwargs)
        output = u''.join(list(generator))
        if encoding is not None:
            return output.encode(encoding)
        return output

    def select(self, path):
        """Return a new stream that contains the events matching the given
        XPath expression.
        
        @param path: a string containing the XPath expression
        """
        from markup.path import Path
        return Path(path).select(self)

    def serialize(self, method='xml', filters=None, **kwargs):
        """Generate strings corresponding to a specific serialization of the
        stream.
        
        Unlike the `render()` method, this method is a generator this returns
        the serialized output incrementally, as opposed to returning a single
        string.
        
        @param method: determines how the stream is serialized; can be either
                       'xml' or 'html', or a custom `Serializer` subclass
        """
        from markup.filters import WhitespaceFilter
        from markup import output
        cls = method
        if isinstance(method, basestring):
            cls = {'xml': output.XMLSerializer,
                   'html': output.HTMLSerializer}[method]
        else:
            assert issubclass(cls, serializers.Serializer)
        serializer = cls(**kwargs)

        stream = self
        if filters is None:
            filters = [WhitespaceFilter()]
        for filter_ in filters:
            stream = filter_(iter(stream))

        return serializer.serialize(stream)

    def __str__(self):
        return self.render()

    def __unicode__(self):
        return self.render(encoding=None)


class Attributes(list):

    def __init__(self, attrib=None):
        list.__init__(self, map(lambda (k, v): (QName(k), v), attrib or []))

    def __contains__(self, name):
        return name in [attr for attr, value in self]

    def get(self, name, default=None):
        for attr, value in self:
            if attr == name:
                return value
        return default

    def remove(self, name):
        for idx, (attr, _) in enumerate(self):
            if attr == name:
                del self[idx]
                break

    def set(self, name, value):
        for idx, (attr, _) in enumerate(self):
            if attr == name:
                self[idx] = (attr, value)
                break
        else:
            self.append((QName(name), value))


class Markup(unicode):
    """Marks a string as being safe for inclusion in HTML/XML output without
    needing to be escaped.
    """
    def __new__(self, text='', *args):
        if args:
            text %= tuple([escape(arg) for arg in args])
        return unicode.__new__(self, text)

    def __add__(self, other):
        return Markup(unicode(self) + Markup.escape(other))

    def __mod__(self, args):
        if not isinstance(args, (list, tuple)):
            args = [args]
        return Markup(unicode.__mod__(self,
                                      tuple([escape(arg) for arg in args])))

    def __mul__(self, num):
        return Markup(unicode(self) * num)

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self)

    def join(self, seq):
        return Markup(unicode(self).join([Markup.escape(item) for item in seq]))

    def stripentities(self, keepxmlentities=False):
        """Return a copy of the text with any character or numeric entities
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
        return Markup(re.sub(r'&(?:#((?:\d+)|(?:[xX][0-9a-fA-F]+));?|(\w+);)',
                             _replace_entity, self))

    def striptags(self):
        """Return a copy of the text with all XML/HTML tags removed."""
        return Markup(re.sub(r'<[^>]*?>', '', self))

    def escape(cls, text, quotes=True):
        """Create a Markup instance from a string and escape special characters
        it may contain (<, >, & and \").
        
        If the `quotes` parameter is set to `False`, the \" character is left
        as is. Escaping quotes is generally only required for strings that are
        to be used in attribute values.
        """
        if isinstance(text, cls):
            return text
        text = unicode(text)
        if not text:
            return cls()
        text = text.replace('&', '&amp;') \
                   .replace('<', '&lt;') \
                   .replace('>', '&gt;')
        if quotes:
            text = text.replace('"', '&#34;')
        return cls(text)
    escape = classmethod(escape)

    def unescape(self):
        """Reverse-escapes &, <, > and \" and returns a `unicode` object."""
        if not self:
            return ''
        return unicode(self).replace('&#34;', '"') \
                            .replace('&gt;', '>') \
                            .replace('&lt;', '<') \
                            .replace('&amp;', '&')

    def plaintext(self, keeplinebreaks=True):
        """Returns the text as a `unicode` string with all entities and tags
        removed.
        """
        text = unicode(self.striptags().stripentities())
        if not keeplinebreaks:
            text = text.replace('\n', ' ')
        return text

    def sanitize(self):
        from markup.filters import HTMLSanitizer
        from markup.input import HTMLParser
        text = StringIO(self.stripentities(keepxmlentities=True))
        return Stream(HTMLSanitizer()(HTMLParser(text)))


escape = Markup.escape

def unescape(text):
    """Reverse-escapes &, <, > and \" and returns a `unicode` object."""
    if not isinstance(text, Markup):
        return text
    return text.unescape()


class Namespace(object):

    def __init__(self, uri):
        self.uri = uri

    def __getitem__(self, name):
        return QName(self.uri + '}' + name)

    __getattr__ = __getitem__

    def __repr__(self):
        return '<Namespace "%s">' % self.uri

    def __str__(self):
        return self.uri

    def __unicode__(self):
        return unicode(self.uri)


class QName(unicode):
    """A qualified element or attribute name.
    
    The unicode value of instances of this class contains the qualified name of
    the element or attribute, in the form `{namespace}localname`. The namespace
    URI can be obtained through the additional `namespace` attribute, while the
    local name can be accessed through the `localname` attribute.
    """
    __slots__ = ['namespace', 'localname']

    def __new__(cls, qname):
        if isinstance(qname, QName):
            return qname

        parts = qname.split('}', 1)
        if qname.find('}') > 0:
            self = unicode.__new__(cls, '{' + qname)
            self.namespace = parts[0]
            self.localname = parts[1]
        else:
            self = unicode.__new__(cls, qname)
            self.namespace = None
            self.localname = qname
        return self
