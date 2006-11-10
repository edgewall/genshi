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

"""This module provides different kinds of serialization methods for XML event
streams.
"""

from itertools import chain
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import re

from genshi.core import escape, Markup, Namespace, QName, StreamEventKind
from genshi.core import DOCTYPE, START, END, START_NS, TEXT, START_CDATA, \
                        END_CDATA, PI, COMMENT, XML_NAMESPACE

__all__ = ['DocType', 'XMLSerializer', 'XHTMLSerializer', 'HTMLSerializer',
           'TextSerializer']


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
    
    >>> from genshi.builder import tag
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
        self.filters = [EmptyTagFilter()]
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
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
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

                for attr, value in attrib + tuple(ns_attrib):
                    attrname = attr.localname
                    if attr.namespace:
                        prefix = ns_mapping.get(attr.namespace)
                        if prefix:
                            attrname = '%s:%s' % (prefix, attrname)
                    buf += [' ', attrname, '="', escape(value), '"']
                ns_attrib = []

                if kind is EMPTY:
                    buf += ['/>']
                else:
                    buf += ['>']

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
    
    >>> from genshi.builder import tag
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
    _PRESERVE_SPACE = frozenset([
        QName('pre'), QName('http://www.w3.org/1999/xhtml}pre'),
        QName('textarea'), QName('http://www.w3.org/1999/xhtml}textarea')
    ])

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
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
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

                for attr, value in chain(attrib, ns_attrib):
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

                if kind is EMPTY:
                    if (tagns and tagns != namespace.uri) \
                            or tag.localname in empty_elems:
                        buf += [' />']
                    else:
                        buf += ['></%s>' % tagname]
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
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(HTMLSerializer()(elem.generate()))
    <div><a href="foo"></a><br><hr noshade></div>
    """

    _NOESCAPE_ELEMS = frozenset([QName('script'),
                                 QName('http://www.w3.org/1999/xhtml}script'),
                                 QName('style'),
                                 QName('http://www.w3.org/1999/xhtml}style')])

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
                                                 self._NOESCAPE_ELEMS))

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
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
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

                    buf += ['>']

                    if kind is EMPTY:
                        if tagname not in empty_elems:
                            buf += ['</%s>' % tagname]

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


class TextSerializer(object):
    """Produces plain text from an event stream.
    
    Only text events are included in the output. Unlike the other serializer,
    special XML characters are not escaped:
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a('<Hello!>', href='foo'), tag.br)
    >>> print elem
    <div><a href="foo">&lt;Hello!&gt;</a><br/></div>
    >>> print ''.join(TextSerializer()(elem.generate()))
    <Hello!>

    If text events contain literal markup (instances of the `Markup` class),
    tags or entities are stripped from the output:
    
    >>> elem = tag.div(Markup('<a href="foo">Hello!</a><br/>'))
    >>> print elem
    <div><a href="foo">Hello!</a><br/></div>
    >>> print ''.join(TextSerializer()(elem.generate()))
    Hello!
    """

    def __call__(self, stream):
        for kind, data, pos in stream:
            if kind is TEXT:
                if type(data) is Markup:
                    data = data.striptags().stripentities()
                yield unicode(data)


class EmptyTagFilter(object):
    """Combines `START` and `STOP` events into `EMPTY` events for elements that
    have no contents.
    """

    EMPTY = StreamEventKind('EMPTY')

    def __call__(self, stream):
        prev = (None, None, None)
        for kind, data, pos in stream:
            if prev[0] is START:
                if kind is END:
                    prev = EMPTY, prev[1], prev[2]
                    yield prev
                    continue
                else:
                    yield prev
            if kind is not START:
                yield kind, data, pos
            prev = kind, data, pos


EMPTY = EmptyTagFilter.EMPTY


class WhitespaceFilter(object):
    """A filter that removes extraneous ignorable white space from the
    stream."""

    def __init__(self, preserve=None, noescape=None):
        """Initialize the filter.
        
        @param preserve: a set or sequence of tag names for which white-space
            should be ignored.
        @param noescape: a set or sequence of tag names for which text content
            should not be escaped
        
        The `noescape` set is expected to refer to elements that cannot contain
        further child elements (such as <style> or <script> in HTML documents).
        """
        if preserve is None:
            preserve = []
        self.preserve = frozenset(preserve)
        if noescape is None:
            noescape = []
        self.noescape = frozenset(noescape)

    def __call__(self, stream, ctxt=None, space=XML_NAMESPACE['space'],
                 trim_trailing_space=re.compile('[ \t]+(?=\n)').sub,
                 collapse_lines=re.compile('\n{2,}').sub):
        mjoin = Markup('').join
        preserve_elems = self.preserve
        preserve = 0
        noescape_elems = self.noescape
        noescape = False

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
                    tag, attrs = data
                    if preserve or (tag in preserve_elems or
                                    attrs.get(space) == 'preserve'):
                        preserve += 1
                    if not noescape and tag in noescape_elems:
                        noescape = True

                elif kind is END:
                    noescape = False
                    if preserve:
                        preserve -= 1

                elif kind is START_CDATA:
                    noescape = True

                elif kind is END_CDATA:
                    noescape = False

                if kind:
                    yield kind, data, pos
