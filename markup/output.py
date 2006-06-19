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

"""This module provides different kinds of serialization methods for XML event
streams.
"""

try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset

from markup.core import Markup, Namespace, QName, Stream
from markup.filters import WhitespaceFilter

__all__ = ['Serializer', 'XMLSerializer', 'HTMLSerializer']


class Serializer(object):
    """Base class for serializers."""

    def serialize(self, stream):
        raise NotImplementedError


class XMLSerializer(Serializer):
    """Produces XML text from an event stream.
    
    >>> from markup.builder import tag
    >>> elem = tag.DIV(tag.A(href='foo'), tag.BR, tag.HR(noshade=True))
    >>> print ''.join(XMLSerializer().serialize(elem.generate()))
    <div><a href="foo"/><br/><hr noshade="True"/></div>
    """

    def serialize(self, stream):
        ns_attrib = []
        ns_mapping = {}

        stream = PushbackIterator(stream)
        for kind, data, pos in stream:

            if kind is Stream.DOCTYPE:
                # FIXME: what if there's no system or public ID in the input?
                yield Markup('<!DOCTYPE %s "%s" "%s">\n' % data)

            elif kind is Stream.START_NS:
                prefix, uri = data
                if uri not in ns_mapping:
                    ns_mapping[uri] = prefix
                    if not prefix:
                        ns_attrib.append((QName('xmlns'), uri))
                    else:
                        ns_attrib.append((QName('xmlns:%s' % prefix), uri))

            elif kind is Stream.START:
                tag, attrib = data

                tagname = tag.localname
                if tag.namespace:
                    try:
                        prefix = ns_mapping[tag.namespace]
                        if prefix:
                            tagname = prefix + ':' + tag.localname
                    except KeyError:
                        ns_attrib.append((QName('xmlns'), tag.namespace))
                buf = ['<', tagname]

                if ns_attrib:
                    attrib.extend(ns_attrib)
                    ns_attrib = []
                for attr, value in attrib:
                    attrname = attr.localname
                    if attr.namespace:
                        try:
                            prefix = ns_mapping[attr.namespace]
                        except KeyError:
                            # FIXME: synthesize a prefix for the attribute?
                            prefix = ''
                        if prefix:
                            attrname = prefix + ':' + attrname
                    buf.append(' %s="%s"' % (attrname, Markup.escape(value)))

                kind, data, pos = stream.next()
                if kind is Stream.END:
                    buf.append('/>')
                else:
                    buf.append('>')
                    stream.pushback((kind, data, pos))

                yield Markup(''.join(buf))

            elif kind is Stream.END:
                tag = data
                tagname = tag.localname
                if tag.namespace:
                    try:
                        prefix = ns_mapping[tag.namespace]
                        if prefix:
                            tagname = prefix + ':' + tag.localname
                    except KeyError:
                        pass
                yield Markup('</%s>' % tagname)

            elif kind is Stream.TEXT:
                yield Markup.escape(data, quotes=False)


class HTMLSerializer(Serializer):
    """Produces HTML text from an event stream.
    
    >>> from markup.builder import tag
    >>> elem = tag.DIV(tag.A(href='foo'), tag.BR, tag.HR(noshade=True))
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

    def serialize(self, stream):
        ns_mapping = {}

        stream = PushbackIterator(stream)
        for kind, data, pos in stream:

            if kind is Stream.DOCTYPE:
                yield Markup('<!DOCTYPE %s "%s" "%s">\n' % data)

            elif kind is Stream.START_NS:
                prefix, uri = data
                if uri not in ns_mapping:
                    ns_mapping[uri] = prefix

            elif kind is Stream.START:
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
                        buf.append(' %s="%s"' % (attr.localname,
                                                 Markup.escape(value)))

                if tag.localname in self._EMPTY_ELEMS:
                    kind, data, pos = stream.next()
                    if kind is not Stream.END:
                        stream.pushback((kind, data, pos))

                yield Markup(''.join(buf + ['>']))

            elif kind is Stream.END:
                tag = data
                if tag.namespace and tag not in self.NAMESPACE:
                    continue # not in the HTML namespace, so don't emit
                yield Markup('</%s>' % tag.localname)

            elif kind is Stream.TEXT:
                yield Markup.escape(data, quotes=False)


class PushbackIterator(object):
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
