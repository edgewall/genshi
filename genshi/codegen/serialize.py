# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software and Michael Bayer <mike_mp@zzzcomputing.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""
Adaptation of genshi.output to deliver output-specific event streams suitable for
Python code generation (i.e. adds a fourth "literal" element to each event), 
given standard Genshi 3-element streams.

While this module is a severe transgression of DRY, reusing the output-specific logic
from the genshi.output module would require de-optimizing the base genshi.output implementations.

The Filters are also stateful and must be created per-generator.
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
from genshi.output import DocType

__all__ = ['XMLSerializeFilter', 'XHTMLSerializeFilter', 'HTMLSerializeFilter']

class XMLSerializeFilter(object):
    """Delivers the given stream with additional XML text added to outgoing events.
    
    """
    _PRESERVE_SPACE = frozenset()

    def __init__(self, doctype=None):
        """Initialize the XML serialize filter.
        
        @param doctype: a `(name, pubid, sysid)` tuple that represents the
            DOCTYPE declaration that should be included at the top of the
            generated output
        @param strip_whitespace: whether extraneous whitespace should be
            stripped from the output
        """
        self.preamble = []
        if doctype:
            self.preamble.append((DOCTYPE, doctype, (None, -1, -1)))
        self.ns_attrib = []
        self.ns_mapping = {XML_NAMESPACE.uri: 'xml'}
        self.have_doctype = False
        self.in_cdata = False

    def __call__(self, stream):
        stream = chain(self.preamble, stream)
        for kind, data, pos in stream:
            if kind is START:
                tag, attrib = data
                tagname = tag.localname
                namespace = tag.namespace
                if namespace:
                    if namespace in self.ns_mapping:
                        prefix = self.ns_mapping[namespace]
                        if prefix:
                            tagname = '%s:%s' % (prefix, tagname)
                    else:
                        self.ns_attrib.append((QName('xmlns'), namespace))
                buf = ['<', tagname]

                for attr, value in attrib + self.ns_attrib:
                    attrname = attr.localname
                    if attr.namespace:
                        prefix = ns_mapping.get(attr.namespace)
                        if prefix:
                            attrname = '%s:%s' % (prefix, attrname)
                    buf += [' ', attrname, '="', escape(value), '"']
                self.ns_attrib = []

                buf += ['>']
                yield kind, data, pos, u''.join(buf)

            elif kind is END:
                tag = data
                tagname = tag.localname
                if tag.namespace:
                    prefix = self.ns_mapping.get(tag.namespace)
                    if prefix:
                        tagname = '%s:%s' % (prefix, tag.localname)
                yield kind, data, pos, u'</%s>' % tagname

            elif kind is TEXT:
                if self.in_cdata:
                    yield kind, data, pos, data
                else:
                    yield kind, data, pos, escape(data, quotes=False)

            elif kind is COMMENT:
                yield kind, data, pos, u'<!--%s-->' % data

            elif kind is DOCTYPE and not self.have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf += [' PUBLIC "%s"']
                elif sysid:
                    buf += [' SYSTEM']
                if sysid:
                    buf += [' "%s"']
                buf += ['>\n']
                yield kind, data, pos, unicode(Markup(''.join(buf), *filter(None, data)))
                self.have_doctype = True

            elif kind is START_NS:
                prefix, uri = data
                if uri not in self.ns_mapping:
                    self.ns_mapping[uri] = prefix
                    if not prefix:
                        self.ns_attrib.append((QName('xmlns'), uri))
                    else:
                        self.ns_attrib.append((QName('xmlns:%s' % prefix), uri))
                    yield kind, data, pos, None

            elif kind is START_CDATA:
                yield kind, data, pos, u'<![CDATA['
                self.in_cdata = True

            elif kind is END_CDATA:
                yield kind, data, pos, u']]>'
                self.in_cdata = False

            elif kind is PI:
                yield kind, data, pos, u'<?%s %s?>' % data
            else:
                # all other events pass-thru
                yield kind, data, pos, None


class XHTMLSerializeFilter(XMLSerializeFilter):
    """Delivers the given stream with additional XHTML text added to outgoing events.
    
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
        raise "TODO"

class HTMLSerializeFilter(XHTMLSerializeFilter):
    """Delivers the given stream with additional HTML text added to outgoing events.
    
    """

    _NOESCAPE_ELEMS = frozenset([QName('script'),
                                 QName('http://www.w3.org/1999/xhtml}script'),
                                 QName('style'),
                                 QName('http://www.w3.org/1999/xhtml}style')])

    def __init__(self, doctype=None):
        """Initialize the HTML serialize filter.
        
        @param doctype: a `(name, pubid, sysid)` tuple that represents the
            DOCTYPE declaration that should be included at the top of the
            generated output
        @param strip_whitespace: whether extraneous whitespace should be
            stripped from the output
        """
        super(HTMLSerializeFilter, self).__init__(doctype)
            
    def __call__(self, stream):
        namespace = self.NAMESPACE
        ns_mapping = {}
        boolean_attrs = self._BOOLEAN_ATTRS
        empty_elems = self._EMPTY_ELEMS
        noescape_elems = self._NOESCAPE_ELEMS
        have_doctype = False
        noescape = False

        stream = chain(self.preamble, stream)
        for kind, data, pos in stream:
            if kind is START:
                tag, attrib = data
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

                if tag.namespace and tag not in namespace:
                    yield kind, data, pos, u''
                else:
                    yield kind, data, pos, u''.join(buf)
                    if tagname in noescape_elems:
                        noescape = True

            elif kind is END:
                if not data.namespace or data in namespace:
                    yield kind, data, pos, u'</%s>' % data.localname
                else:
                    yield kind, data, pos, u''
                noescape = False

            elif kind is TEXT:
                if noescape:
                    yield kind, data, pos, data
                else:
                    yield kind, data, pos, escape(data, quotes=False)

            elif kind is COMMENT:
                yield kind, data, pos, u'<!--%s-->' % data

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
                yield kind, data, pos, unicode(Markup(''.join(buf), *filter(None, data)))
                have_doctype = True

            elif kind is START_NS and data[1] not in ns_mapping:
                ns_mapping[data[1]] = data[0]
                yield kind, data, pos, None
            elif kind is PI:
                yield kind, data, pos, u'<?%s %s?>' % data
            else:
                # all other events pass-thru
                yield kind, data, pos, None

class TextSerializeFilter(object):
    pass    
