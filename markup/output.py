# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://markup.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://markup.edgewall.org/log/.

"""This module provides different kinds of serialization methods for XML event
streams.
"""

try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
from itertools import chain

from markup.core import escape, Markup, Namespace, QName
from markup.core import DOCTYPE, START, END, START_NS, END_NS, TEXT

__all__ = ['Serializer', 'XMLSerializer', 'HTMLSerializer']


class Serializer(object):
    """Base class for serializers."""

    def serialize(self, stream):
        """Must be implemented by concrete subclasses to serialize the given
        stream.
        
        This method must be implemented as a generator, producing the
        serialized output incrementally as unicode strings.
        """
        raise NotImplementedError


class DocType(object):
    """Defines a number of commonly used DOCTYPE declarations as constants."""

    HTML_STRICT = ('html', '-//W3C//DTD HTML 4.01//EN',
                   'http://www.w3.org/TR/html4/strict.dtd')
    HTML_TRANSITIONAL = ('html', '-//W3C//DTD HTML 4.01 Transitional//EN',
                         'http://www.w3.org/TR/html4/loose.dtd')
    HTML = HTML_STRICT

    XHTML_STRICT = ('html', '-//W3C//DTD XHTML 1.0 Strict//EN',
                    'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd')
    XHTML_TRANSITIONAL = ('html', '-//W3C//DTD XHTML 1.0 Transitional//EN',
                          'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd')
    XHTML = XHTML_STRICT


class XMLSerializer(Serializer):
    """Produces XML text from an event stream.
    
    >>> from markup.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(XMLSerializer().serialize(elem.generate()))
    <div><a href="foo"/><br/><hr noshade="True"/></div>
    """
    def __init__(self, doctype=None):
        """Initialize the XML serializer.
        
        @param doctype: a `(name, pubid, sysid)` tuple that represents the
            DOCTYPE declaration that should be included at the top of the
            generated output
        """
        self.preamble = []
        if doctype:
            self.preamble.append((DOCTYPE, doctype, (None, -1, -1)))

    def serialize(self, stream):
        have_doctype = False
        ns_attrib = []
        ns_mapping = {}

        stream = _PushbackIterator(chain(self.preamble, stream))
        for kind, data, pos in stream:

            if kind is DOCTYPE:
                if not have_doctype:
                    name, pubid, sysid = data
                    buf = ['<!DOCTYPE %s']
                    if pubid:
                        buf.append(' PUBLIC "%s"')
                    elif sysid:
                        buf.append(' SYSTEM')
                    if sysid:
                        buf.append(' "%s"')
                    buf.append('>\n')
                    yield Markup(''.join(buf), *filter(None, data))
                    have_doctype = True

            elif kind is START_NS:
                prefix, uri = data
                if uri not in ns_mapping:
                    ns_mapping[uri] = prefix
                    if not prefix:
                        ns_attrib.append((QName('xmlns'), uri))
                    else:
                        ns_attrib.append((QName('xmlns:%s' % prefix), uri))

            elif kind is START:
                tag, attrib = data

                tagname = tag.localname
                if tag.namespace:
                    try:
                        prefix = ns_mapping[tag.namespace]
                        if prefix:
                            tagname = '%s:%s' % (prefix, tag.localname)
                    except KeyError:
                        ns_attrib.append((QName('xmlns'), tag.namespace))
                buf = ['<%s' % tagname]

                if ns_attrib:
                    attrib.extend(ns_attrib)
                    ns_attrib = []
                for attr, value in attrib:
                    attrname = attr.localname
                    if attr.namespace:
                        prefix = ns_mapping.get(attr.namespace)
                        if prefix:
                            attrname = '%s:%s' % (prefix, attrname)
                    buf.append(' %s="%s"' % (attrname, escape(value)))

                kind, data, pos = stream.next()
                if kind is END:
                    buf.append('/>')
                else:
                    buf.append('>')
                    stream.pushback((kind, data, pos))

                yield Markup(''.join(buf))

            elif kind is END:
                tag = data
                tagname = tag.localname
                if tag.namespace:
                    prefix = ns_mapping.get(tag.namespace)
                    if prefix:
                        tagname = '%s:%s' % (prefix, tag.localname)
                yield Markup('</%s>' % tagname)

            elif kind is TEXT:
                yield escape(data, quotes=False)


class HTMLSerializer(Serializer):
    """Produces HTML text from an event stream.
    
    >>> from markup.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(HTMLSerializer().serialize(elem.generate()))
    <div><a href="foo"></a><br><hr noshade></div>
    """

    NAMESPACE = Namespace('http://www.w3.org/1999/xhtml')

    _EMPTY_ELEMS = frozenset(['area', 'base', 'basefont', 'br', 'col', 'frame',
                              'hr', 'img', 'input', 'isindex', 'link', 'meta',
                              'param'])
    _BOOLEAN_ATTRS = frozenset(['selected', 'checked', 'compact', 'declare',
                                'defer', 'disabled', 'ismap', 'multiple',
                                'nohref', 'noresize', 'noshade', 'nowrap'])

    def __init__(self, doctype=None):
        """Initialize the HTML serializer.
        
        @param doctype: a `(name, pubid, sysid)` tuple that represents the
            DOCTYPE declaration that should be included at the top of the
            generated output
        """
        self.preamble = []
        if doctype:
            self.preamble.append((DOCTYPE, doctype, (None, -1, -1)))

    def serialize(self, stream):
        have_doctype = False
        ns_mapping = {}

        stream = _PushbackIterator(chain(self.preamble, stream))
        for kind, data, pos in stream:

            if kind is DOCTYPE:
                if not have_doctype:
                    name, pubid, sysid = data
                    buf = ['<!DOCTYPE %s']
                    if pubid:
                        buf.append(' PUBLIC "%s"')
                    elif sysid:
                        buf.append(' SYSTEM')
                    if sysid:
                        buf.append(' "%s"')
                    buf.append('>\n')
                    yield Markup(''.join(buf), *filter(None, data))
                    have_doctype = True

            elif kind is START_NS:
                prefix, uri = data
                if uri not in ns_mapping:
                    ns_mapping[uri] = prefix

            elif kind is START:
                tag, attrib = data
                if tag.namespace and tag not in self.NAMESPACE:
                    continue # not in the HTML namespace, so don't emit
                buf = ['<', tag.localname]
                for attr, value in attrib:
                    if attr.namespace and attr not in self.NAMESPACE:
                        continue # not in the HTML namespace, so don't emit
                    if attr.localname in self._BOOLEAN_ATTRS:
                        if value:
                            buf.append(' %s' % attr.localname)
                    else:
                        buf.append(' %s="%s"' % (attr.localname, escape(value)))

                if tag.localname in self._EMPTY_ELEMS:
                    kind, data, pos = stream.next()
                    if kind is not END:
                        stream.pushback((kind, data, pos))

                yield Markup(''.join(buf + ['>']))

            elif kind is END:
                tag = data
                if tag.namespace and tag not in self.NAMESPACE:
                    continue # not in the HTML namespace, so don't emit
                yield Markup('</%s>' % tag.localname)

            elif kind is TEXT:
                yield escape(data, quotes=False)


class _PushbackIterator(object):
    """A simple wrapper for iterators that allows pushing items back on the
    queue via the `pushback()` method.
    
    That can effectively be used to peek at the next item."""
    __slots__ = ['iterable', 'buf']

    def __init__(self, iterable):
        self.iterable = iter(iterable)
        self.buf = []

    def __iter__(self):
        return self

    def next(self):
        if self.buf:
            return self.buf.pop(0)
        return self.iterable.next()

    def pushback(self, item):
        self.buf.append(item)
