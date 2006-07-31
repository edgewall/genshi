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

"""Implementation of a number of stream filters."""

from itertools import chain
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import re

from markup.core import Attributes, Markup, Namespace, escape, stripentities
from markup.core import END, END_NS, START, START_NS, TEXT
from markup.path import Path

__all__ = ['IncludeFilter', 'WhitespaceFilter', 'HTMLSanitizer']


class IncludeFilter(object):
    """Template filter providing (very) basic XInclude support
    (see http://www.w3.org/TR/xinclude/) in templates.
    """

    NAMESPACE = Namespace('http://www.w3.org/2001/XInclude')

    def __init__(self, loader):
        """Initialize the filter.
        
        @param loader: the `TemplateLoader` to use for resolving references to
            external template files
        """
        self.loader = loader

    def __call__(self, stream, ctxt=None, ns_prefixes=None):
        """Filter the stream, processing any XInclude directives it may
        contain.
        
        @param ctxt: the template context
        @param stream: the markup event stream to filter
        """
        from markup.template import Template, TemplateError, TemplateNotFound

        if ns_prefixes is None:
            ns_prefixes = []
        in_fallback = False
        include_href, fallback_stream = None, None
        namespace = self.NAMESPACE

        for kind, data, pos in stream:

            if kind is START and not in_fallback and data[0] in namespace:
                tag, attrib = data
                if tag.localname == 'include':
                    include_href = attrib.get('href')
                elif tag.localname == 'fallback':
                    in_fallback = True
                    fallback_stream = []

            elif kind is END and data in namespace:
                if data.localname == 'include':
                    try:
                        if not include_href:
                            raise TemplateError('Include misses required '
                                                'attribute "href"')
                        template = self.loader.load(include_href,
                                                    relative_to=pos[0])
                        for event in template.generate(ctxt):
                            yield event

                    except TemplateNotFound:
                        if fallback_stream is None:
                            raise
                        for event in fallback_stream:
                            yield event

                    include_href = None
                    fallback_stream = None

                elif data.localname == 'fallback':
                    in_fallback = False

            elif in_fallback:
                fallback_stream.append((kind, data, pos))

            elif kind is START_NS and data[1] == namespace:
                ns_prefixes.append(data[0])

            elif kind is END_NS and data in ns_prefixes:
                ns_prefixes.pop()

            else:
                yield kind, data, pos


class WhitespaceFilter(object):
    """A filter that removes extraneous white space from the stream.

    TODO:
     * Support for xml:space
    """
    _TRAILING_SPACE = re.compile('[ \t]+(?=\n)')
    _LINE_COLLAPSE = re.compile('\n{2,}')

    def __call__(self, stream, ctxt=None):
        trim_trailing_space = self._TRAILING_SPACE.sub
        collapse_lines = self._LINE_COLLAPSE.sub
        mjoin = Markup('').join

        textbuf = []
        for kind, data, pos in chain(stream, [(None, None, None)]):
            if kind is TEXT:
                textbuf.append(data)
            else:
                if textbuf:
                    if len(textbuf) > 1:
                        output = Markup(collapse_lines('\n',
                            trim_trailing_space('',
                                mjoin(textbuf, escape_quotes=False))))
                        del textbuf[:]
                        yield TEXT, output, pos
                    else:
                        output = Markup(collapse_lines('\n',
                            trim_trailing_space('',
                                escape(textbuf.pop(), quotes=False))))
                        yield TEXT, output, pos
                if kind is not None:
                    yield kind, data, pos


class HTMLSanitizer(object):
    """A filter that removes potentially dangerous HTML tags and attributes
    from the stream.
    """

    _SAFE_TAGS = frozenset(['a', 'abbr', 'acronym', 'address', 'area', 'b',
        'big', 'blockquote', 'br', 'button', 'caption', 'center', 'cite',
        'code', 'col', 'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt',
        'em', 'fieldset', 'font', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'hr', 'i', 'img', 'input', 'ins', 'kbd', 'label', 'legend', 'li', 'map',
        'menu', 'ol', 'optgroup', 'option', 'p', 'pre', 'q', 's', 'samp',
        'select', 'small', 'span', 'strike', 'strong', 'sub', 'sup', 'table',
        'tbody', 'td', 'textarea', 'tfoot', 'th', 'thead', 'tr', 'tt', 'u',
        'ul', 'var'])

    _SAFE_ATTRS = frozenset(['abbr', 'accept', 'accept-charset', 'accesskey',
        'action', 'align', 'alt', 'axis', 'bgcolor', 'border', 'cellpadding',
        'cellspacing', 'char', 'charoff', 'charset', 'checked', 'cite', 'class',
        'clear', 'cols', 'colspan', 'color', 'compact', 'coords', 'datetime',
        'dir', 'disabled', 'enctype', 'for', 'frame', 'headers', 'height',
        'href', 'hreflang', 'hspace', 'id', 'ismap', 'label', 'lang',
        'longdesc', 'maxlength', 'media', 'method', 'multiple', 'name',
        'nohref', 'noshade', 'nowrap', 'prompt', 'readonly', 'rel', 'rev',
        'rows', 'rowspan', 'rules', 'scope', 'selected', 'shape', 'size',
        'span', 'src', 'start', 'style', 'summary', 'tabindex', 'target',
        'title', 'type', 'usemap', 'valign', 'value', 'vspace', 'width'])
    _URI_ATTRS = frozenset(['action', 'background', 'dynsrc', 'href', 'lowsrc',
        'src'])
    _SAFE_SCHEMES = frozenset(['file', 'ftp', 'http', 'https', 'mailto', None])

    def __call__(self, stream, ctxt=None):
        waiting_for = None

        for kind, data, pos in stream:
            if kind is START:
                if waiting_for:
                    continue
                tag, attrib = data
                if tag not in self._SAFE_TAGS:
                    waiting_for = tag
                    continue

                new_attrib = []
                for attr, value in attrib:
                    value = stripentities(value)
                    if attr not in self._SAFE_ATTRS:
                        continue
                    elif attr in self._URI_ATTRS:
                        # Don't allow URI schemes such as "javascript:"
                        if self._get_scheme(value) not in self._SAFE_SCHEMES:
                            continue
                    elif attr == 'style':
                        # Remove dangerous CSS declarations from inline styles
                        decls = []
                        for decl in filter(None, value.split(';')):
                            is_evil = False
                            if 'expression' in decl:
                                is_evil = True
                            for m in re.finditer(r'url\s*\(([^)]+)', decl):
                                if self._get_scheme(m.group(1)) not in self._SAFE_SCHEMES:
                                    is_evil = True
                                    break
                            if not is_evil:
                                decls.append(decl.strip())
                        if not decls:
                            continue
                        value = '; '.join(decls)
                    new_attrib.append((attr, value))

                yield kind, (tag, new_attrib), pos

            elif kind is END:
                tag = data
                if waiting_for:
                    if waiting_for == tag:
                        waiting_for = None
                else:
                    yield kind, data, pos

            else:
                if not waiting_for:
                    yield kind, data, pos

    def _get_scheme(self, text):
        if ':' not in text:
            return None
        chars = [char for char in text.split(':', 1)[0] if char.isalnum()]
        return ''.join(chars).lower()
