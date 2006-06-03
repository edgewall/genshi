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

"""Implementation of a number of stream filters."""

try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import re

from markup.core import Attributes, Markup, Stream
from markup.path import Path

__all__ = ['EvalFilter', 'IncludeFilter', 'MatchFilter', 'WhitespaceFilter',
           'HTMLSanitizer']


class EvalFilter(object):
    """Responsible for evaluating expressions in a template."""

    def __call__(self, stream, ctxt=None):
        for kind, data, pos in stream:

            if kind is Stream.START:
                # Attributes may still contain expressions in start tags at
                # this point, so do some evaluation
                tag, attrib = data
                new_attrib = []
                for name, substream in attrib:
                    if isinstance(substream, basestring):
                        value = substream
                    else:
                        values = []
                        for subkind, subdata, subpos in substream:
                            if subkind is Stream.EXPR:
                                values.append(subdata.evaluate(ctxt))
                            else:
                                values.append(subdata)
                        value = filter(lambda x: x is not None, values)
                        if not value:
                            continue
                    new_attrib.append((name, ''.join(value)))
                yield kind, (tag, Attributes(new_attrib)), pos

            elif kind is Stream.EXPR:
                result = data.evaluate(ctxt)
                if result is None:
                    continue

                # First check for a string, otherwise the iterable
                # test below succeeds, and the string will be
                # chopped up into characters
                if isinstance(result, basestring):
                    yield Stream.TEXT, result, pos
                else:
                    # Test if the expression evaluated to an
                    # iterable, in which case we yield the
                    # individual items
                    try:
                        yield Stream.SUB, ([], iter(result)), pos
                    except TypeError:
                        # Neither a string nor an iterable, so just
                        # pass it through
                        yield Stream.TEXT, unicode(result), pos

            else:
                yield kind, data, pos


class IncludeFilter(object):
    """Template filter providing (very) basic XInclude support
    (see http://www.w3.org/TR/xinclude/) in templates.
    """

    _NAMESPACE = 'http://www.w3.org/2001/XInclude'

    def __init__(self, loader):
        """Initialize the filter.
        
        @param loader: the `TemplateLoader` to use for resolving references to
            external template files
        """
        self.loader = loader

    def __call__(self, stream, ctxt=None):
        """Filter the stream, processing any XInclude directives it may
        contain.
        
        @param ctxt: the template context
        @param stream: the markup event stream to filter
        """
        from markup.template import TemplateError, TemplateNotFound

        in_fallback = False
        include_href, fallback_stream = None, None
        indent = 0

        for kind, data, pos in stream:

            if kind is Stream.START and data[0].namespace == self._NAMESPACE \
                    and not in_fallback:
                tag, attrib = data
                if tag.localname == 'include':
                    include_href = attrib.get('href')
                    indent = pos[1]
                elif tag.localname == 'fallback':
                    in_fallback = True
                    fallback_stream = []

            elif kind is Stream.END and data.namespace == self._NAMESPACE:
                if data.localname == 'include':
                    try:
                        if not include_href:
                            raise TemplateError('Include misses required '
                                                'attribute "href"')
                        template = self.loader.load(include_href)
                        for ikind, idata, ipos in template.generate(ctxt):
                            # Fixup indentation of included markup
                            if ikind is Stream.TEXT:
                                idata = idata.replace('\n', '\n' + ' ' * indent)
                            yield ikind, idata, ipos

                        # If the included template defines any filters added at
                        # runtime (such as py:match templates), those need to be
                        # applied to the including template, too.
                        for filter_ in template.filters:
                            stream = filter_(stream, ctxt)

                    except TemplateNotFound:
                        if fallback_stream is None:
                            raise
                        for event in fallback_stream:
                            yield event

                    include_href = None
                    fallback_stream = None
                    indent = 0
                    break
                elif data.localname == 'fallback':
                    in_fallback = False

            elif in_fallback:
                fallback_stream.append((kind, data, pos))

            elif kind is Stream.START_NS and data[1] == self._NAMESPACE:
                continue

            else:
                yield kind, data, pos
        else:
            # The loop exited normally, so there shouldn't be further events to
            # process
            return

        for event in self(stream, ctxt):
            yield event


class MatchFilter(object):
    """A filter that delegates to a given handler function when the input stream
    matches some path expression.
    """

    def __init__(self, path, handler):
        self.path = Path(path)
        self.handler = handler

    def __call__(self, stream, ctxt=None):
        test = self.path.test()
        for kind, data, pos in stream:
            result = test(kind, data, pos)
            if result is True:
                content = [(kind, data, pos)]
                depth = 1
                while depth > 0:
                    ev = stream.next()
                    if ev[0] is Stream.START:
                        depth += 1
                    elif ev[0] is Stream.END:
                        depth -= 1
                    content.append(ev)
                    test(*ev)

                yield (Stream.SUB,
                       ([lambda stream, ctxt: self.handler(content, ctxt)], []),
                       pos)
            else:
                yield kind, data, pos


class WhitespaceFilter(object):
    """A filter that removes extraneous white space from the stream.

    Todo:
     * Support for xml:space
    """

    _TRAILING_SPACE = re.compile('[ \t]+(?=\n)')
    _LINE_COLLAPSE = re.compile('\n{2,}')

    def __call__(self, stream, ctxt=None):
        textbuf = []
        prev_kind = None
        for kind, data, pos in stream:
            if kind is Stream.TEXT:
                textbuf.append(data)
            elif prev_kind is Stream.TEXT:
                text = ''.join(textbuf)
                text = self._TRAILING_SPACE.sub('', text)
                text = self._LINE_COLLAPSE.sub('\n', text)
                yield Stream.TEXT, text, pos
                del textbuf[:]
            prev_kind = kind
            if kind is not Stream.TEXT:
                yield kind, data, pos

        if textbuf:
            text = self._LINE_COLLAPSE.sub('\n', ''.join(textbuf))
            yield Stream.TEXT, text, pos


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
        'action', 'align', 'alt', 'axis', 'border', 'cellpadding',
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
            if kind is Stream.START:
                if waiting_for:
                    continue
                tag, attrib = data
                if tag not in self._SAFE_TAGS:
                    waiting_for = tag
                    continue

                new_attrib = []
                for attr, value in attrib:
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

            elif kind is Stream.END:
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
