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

from itertools import chain
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import re

from markup.core import escape, Markup, Namespace, QName
from markup.core import DOCTYPE, START, END, START_NS, TEXT, START_CDATA, \
                        END_CDATA, PI, COMMENT, XML_NAMESPACE

__all__ = ['Serializer', 'XMLSerializer', 'HTMLSerializer']


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


class XMLSerializer(object):
    """Produces XML text from an event stream.
    
    >>> from markup.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(XMLSerializer()(elem.generate()))
    <div><a href="foo"/><br/><hr noshade="True"/></div>
    """

    _PRESERVE_SPACE = frozenset()

    def __init__(self, doctype=None, strip_whitespace=True):
        """Initialize the XML serializer.
        
        @param doctype: a `(name, pubid, sysid)` tuple that represents the
            DOCTYPE declaration that should be included at the top of the
            generated output
        @param strip_whitespace: whether extraneous whitespace should be
            stripped from the output
        """
        self.preamble = []
        if doctype:
            self.preamble.append((DOCTYPE, doctype, (None, -1, -1)))
        self.filters = []
        if strip_whitespace:
            self.filters.append(WhitespaceFilter(self._PRESERVE_SPACE))

    def __call__(self, stream):
        ns_attrib = []
        ns_mapping = {XML_NAMESPACE.uri: 'xml'}
        have_doctype = False
        in_cdata = False

        stream = chain(self.preamble, stream)
        for filter_ in self.filters:
            stream = filter_(stream)
        stream = _PushbackIterator(stream)
        pushback = stream.pushback
        for kind, data, pos in stream:

            if kind is START:
                tag, attrib = data

                tagname = tag.localname
                namespace = tag.namespace
                if namespace:
                    if namespace in ns_mapping:
                        prefix = ns_mapping[namespace]
                        if prefix:
                            tagname = '%s:%s' % (prefix, tagname)
                    else:
                        ns_attrib.append((QName('xmlns'), namespace))
                buf = ['<', tagname]

                for attr, value in attrib + ns_attrib:
                    attrname = attr.localname
                    if attr.namespace:
                        prefix = ns_mapping.get(attr.namespace)
                        if prefix:
                            attrname = '%s:%s' % (prefix, attrname)
                    buf += [' ', attrname, '="', escape(value), '"']
                ns_attrib = []

                kind, data, pos = stream.next()
                if kind is END:
                    buf += ['/>']
                else:
                    buf += ['>']
                    pushback((kind, data, pos))

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
                if in_cdata:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf += [' PUBLIC "%s"']
                elif sysid:
                    buf += [' SYSTEM']
                if sysid:
                    buf += [' "%s"']
                buf += ['>\n']
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

            elif kind is START_CDATA:
                yield Markup('<![CDATA[')
                in_cdata = True

            elif kind is END_CDATA:
                yield Markup(']]>')
                in_cdata = False

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class XHTMLSerializer(XMLSerializer):
    """Produces XHTML text from an event stream.
    
    >>> from markup.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(XHTMLSerializer()(elem.generate()))
    <div><a href="foo"></a><br /><hr noshade="noshade" /></div>
    """

    NAMESPACE = Namespace('http://www.w3.org/1999/xhtml')

    _EMPTY_ELEMS = frozenset(['area', 'base', 'basefont', 'br', 'col', 'frame',
                              'hr', 'img', 'input', 'isindex', 'link', 'meta',
                              'param'])
    _BOOLEAN_ATTRS = frozenset(['selected', 'checked', 'compact', 'declare',
                                'defer', 'disabled', 'ismap', 'multiple',
                                'nohref', 'noresize', 'noshade', 'nowrap'])
    _PRESERVE_SPACE = frozenset([QName('pre'), QName('textarea')])

    def __call__(self, stream):
        namespace = self.NAMESPACE
        ns_attrib = []
        ns_mapping = {XML_NAMESPACE.uri: 'xml'}
        boolean_attrs = self._BOOLEAN_ATTRS
        empty_elems = self._EMPTY_ELEMS
        have_doctype = False
        in_cdata = False

        stream = chain(self.preamble, stream)
        for filter_ in self.filters:
            stream = filter_(stream)
        stream = _PushbackIterator(stream)
        pushback = stream.pushback
        for kind, data, pos in stream:

            if kind is START:
                tag, attrib = data

                tagname = tag.localname
                tagns = tag.namespace
                if tagns:
                    if tagns in ns_mapping:
                        prefix = ns_mapping[tagns]
                        if prefix:
                            tagname = '%s:%s' % (prefix, tagname)
                    else:
                        ns_attrib.append((QName('xmlns'), tagns))
                buf = ['<', tagname]

                for attr, value in attrib + ns_attrib:
                    attrname = attr.localname
                    if attr.namespace:
                        prefix = ns_mapping.get(attr.namespace)
                        if prefix:
                            attrname = '%s:%s' % (prefix, attrname)
                    if attrname in boolean_attrs:
                        if value:
                            buf += [' ', attrname, '="', attrname, '"']
                    else:
                        buf += [' ', attrname, '="', escape(value), '"']
                ns_attrib = []

                if (tagns and tagns != namespace) or tagname in empty_elems:
                    kind, data, pos = stream.next()
                    if kind is END:
                        buf += [' />']
                    else:
                        buf += ['>']
                        pushback((kind, data, pos))
                else:
                    buf += ['>']

                yield Markup(''.join(buf))

            elif kind is END:
                tag = data
                tagname = tag.localname
                if tag.namespace:
                    prefix = ns_mapping.get(tag.namespace)
                    if prefix:
                        tagname = '%s:%s' % (prefix, tagname)
                yield Markup('</%s>' % tagname)

            elif kind is TEXT:
                if in_cdata:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf += [' PUBLIC "%s"']
                elif sysid:
                    buf += [' SYSTEM']
                if sysid:
                    buf += [' "%s"']
                buf += ['>\n']
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

            elif kind is START_CDATA:
                yield Markup('<![CDATA[')
                in_cdata = True

            elif kind is END_CDATA:
                yield Markup(']]>')
                in_cdata = False

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class HTMLSerializer(XHTMLSerializer):
    """Produces HTML text from an event stream.
    
    >>> from markup.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(HTMLSerializer()(elem.generate()))
    <div><a href="foo"></a><br><hr noshade></div>
    """

    _NOESCAPE_ELEMS = frozenset([QName('script'), QName('style')])

    def __init__(self, doctype=None, strip_whitespace=True):
        """Initialize the HTML serializer.
        
        @param doctype: a `(name, pubid, sysid)` tuple that represents the
            DOCTYPE declaration that should be included at the top of the
            generated output
        @param strip_whitespace: whether extraneous whitespace should be
            stripped from the output
        """
        super(HTMLSerializer, self).__init__(doctype, False)
        if strip_whitespace:
            self.filters.append(WhitespaceFilter(self._PRESERVE_SPACE,
                                                 self._NOESCAPE_ELEMS, True))

    def __call__(self, stream):
        namespace = self.NAMESPACE
        ns_mapping = {}
        boolean_attrs = self._BOOLEAN_ATTRS
        empty_elems = self._EMPTY_ELEMS
        noescape_elems = self._NOESCAPE_ELEMS
        have_doctype = False
        noescape = False

        stream = chain(self.preamble, stream)
        for filter_ in self.filters:
            stream = filter_(stream)
        stream = _PushbackIterator(stream)
        pushback = stream.pushback
        for kind, data, pos in stream:

            if kind is START:
                tag, attrib = data
                if not tag.namespace or tag in namespace:
                    tagname = tag.localname
                    buf = ['<', tagname]

                    for attr, value in attrib:
                        attrname = attr.localname
                        if not attr.namespace or attr in namespace:
                            if attrname in boolean_attrs:
                                if value:
                                    buf += [' ', attrname]
                            else:
                                buf += [' ', attrname, '="', escape(value), '"']

                    if tagname in empty_elems:
                        kind, data, pos = stream.next()
                        if kind is not END:
                            pushback((kind, data, pos))

                    buf += ['>']
                    yield Markup(''.join(buf))

                    if tagname in noescape_elems:
                        noescape = True

            elif kind is END:
                tag = data
                if not tag.namespace or tag in namespace:
                    yield Markup('</%s>' % tag.localname)

                noescape = False

            elif kind is TEXT:
                if noescape:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf += [' PUBLIC "%s"']
                elif sysid:
                    buf += [' SYSTEM']
                if sysid:
                    buf += [' "%s"']
                buf += ['>\n']
                yield Markup(''.join(buf), *filter(None, data))
                have_doctype = True

            elif kind is START_NS and data[1] not in ns_mapping:
                ns_mapping[data[1]] = data[0]

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class WhitespaceFilter(object):
    """A filter that removes extraneous ignorable white space from the
    stream."""

    _TRAILING_SPACE = re.compile('[ \t]+(?=\n)')
    _LINE_COLLAPSE = re.compile('\n{2,}')
    _XML_SPACE = XML_NAMESPACE['space']

    def __init__(self, preserve=None, noescape=None, escape_cdata=False):
        """Initialize the filter.
        
        @param preserve: a set or sequence of tag names for which white-space
            should be ignored.
        @param noescape: a set or sequence of tag names for which text content
            should not be escaped
        
        Both the `preserve` and `noescape` sets are expected to refer to
        elements that cannot contain further child elements.
        """
        if preserve is None:
            preserve = []
        self.preserve = frozenset(preserve)
        if noescape is None:
            noescape = []
        self.noescape = frozenset(noescape)
        self.escape_cdata = escape_cdata

    def __call__(self, stream, ctxt=None):
        trim_trailing_space = self._TRAILING_SPACE.sub
        collapse_lines = self._LINE_COLLAPSE.sub
        xml_space = self._XML_SPACE
        mjoin = Markup('').join
        preserve_elems = self.preserve
        preserve = False
        noescape_elems = self.noescape
        noescape = False
        escape_cdata = self.escape_cdata

        textbuf = []
        push_text = textbuf.append
        pop_text = textbuf.pop
        for kind, data, pos in chain(stream, [(None, None, None)]):
            if kind is TEXT:
                if noescape:
                    data = Markup(data)
                push_text(data)
            else:
                if textbuf:
                    if len(textbuf) > 1:
                        text = mjoin(textbuf, escape_quotes=False)
                        del textbuf[:]
                    else:
                        text = escape(pop_text(), quotes=False)
                    if not preserve:
                        text = collapse_lines('\n', trim_trailing_space('', text))
                    yield TEXT, Markup(text), pos

                if kind is START:
                    tag, attrib = data
                    if tag.localname in preserve_elems or \
                            data[1].get(xml_space) == 'preserve':
                        preserve = True

                    if tag.localname in noescape_elems:
                        noescape = True

                elif kind is END:
                    preserve = noescape = False

                elif kind is START_CDATA and not escape_cdata:
                    noescape = True

                elif kind is END_CDATA and not escape_cdata:
                    noescape = False

                if kind:
                    yield kind, data, pos


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
