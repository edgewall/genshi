# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Implementation of a number of stream filters."""

try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import re

from genshi.core import Attrs, QName, stripentities
from genshi.core import END, START, TEXT

__all__ = ['HTMLFormFiller', 'HTMLSanitizer']
__docformat__ = 'restructuredtext en'


class HTMLFormFiller(object):
    """A stream filter that can populate HTML forms from a dictionary of values.
    
    >>> from genshi.input import HTML
    >>> html = HTML('''<form>
    ...   <p><input type="text" name="foo" /></p>
    ... </form>''')
    >>> filler = HTMLFormFiller(data={'foo': 'bar'})
    >>> print html | filler
    <form>
      <p><input type="text" name="foo" value="bar"/></p>
    </form>
    """
    # TODO: only select the first radio button, and the first select option
    #       (if not in a multiple-select)
    # TODO: only apply to elements in the XHTML namespace (or no namespace)?

    def __init__(self, name=None, id=None, data=None):
        """Create the filter.
        
        :param name: The name of the form that should be populated. If this
                     parameter is given, only forms where the ``name`` attribute
                     value matches the parameter are processed.
        :param id: The ID of the form that should be populated. If this
                   parameter is given, only forms where the ``id`` attribute
                   value matches the parameter are processed.
        :param data: The dictionary of form values, where the keys are the names
                     of the form fields, and the values are the values to fill
                     in.
        """
        self.name = name
        self.id = id
        if data is None:
            data = {}
        self.data = data

    def __call__(self, stream):
        """Apply the filter to the given stream.
        
        :param stream: the markup event stream to filter
        """
        in_form = in_select = in_option = in_textarea = False
        select_value = option_value = textarea_value = None
        option_start = option_text = None

        for kind, data, pos in stream:

            if kind is START:
                tag, attrs = data
                tagname = tag.localname

                if tagname == 'form' and (
                        self.name and attrs.get('name') == self.name or
                        self.id and attrs.get('id') == self.id or
                        not (self.id or self.name)):
                    in_form = True

                elif in_form:
                    if tagname == 'input':
                        type = attrs.get('type')
                        if type in ('checkbox', 'radio'):
                            name = attrs.get('name')
                            if name and name in self.data:
                                value = self.data[name]
                                declval = attrs.get('value')
                                checked = False
                                if isinstance(value, (list, tuple)):
                                    if declval:
                                        checked = declval in [str(v) for v
                                                              in value]
                                    else:
                                        checked = bool(filter(None, value))
                                else:
                                    if declval:
                                        checked = declval == str(value)
                                    elif type == 'checkbox':
                                        checked = bool(value)
                                if checked:
                                    attrs |= [(QName('checked'), 'checked')]
                                elif 'checked' in attrs:
                                    attrs -= 'checked'
                        elif type in (None, 'hidden', 'text'):
                            name = attrs.get('name')
                            if name and name in self.data:
                                value = self.data[name]
                                if isinstance(value, (list, tuple)):
                                    value = value[0]
                                if value is not None:
                                    attrs |= [(QName('value'), unicode(value))]
                    elif tagname == 'select':
                        name = attrs.get('name')
                        if name in self.data:
                            select_value = self.data[name]
                            in_select = True
                    elif tagname == 'textarea':
                        name = attrs.get('name')
                        if name in self.data:
                            textarea_value = self.data.get(name)
                            if isinstance(textarea_value, (list, tuple)):
                                textarea_value = textarea_value[0]
                            in_textarea = True
                    elif in_select and tagname == 'option':
                        option_start = kind, data, pos
                        option_value = attrs.get('value')
                        in_option = True
                        continue
                yield kind, (tag, attrs), pos

            elif in_form and kind is TEXT:
                if in_select and in_option:
                    if option_value is None:
                        option_value = data
                    option_text = kind, data, pos
                    continue
                elif in_textarea:
                    continue
                yield kind, data, pos

            elif in_form and kind is END:
                tagname = data.localname
                if tagname == 'form':
                    in_form = False
                elif tagname == 'select':
                    in_select = False
                    select_value = None
                elif in_select and tagname == 'option':
                    if isinstance(select_value, (tuple, list)):
                        selected = option_value in [str(v) for v
                                                    in select_value]
                    else:
                        selected = option_value == str(select_value)
                    okind, (tag, attrs), opos = option_start
                    if selected:
                        attrs |= [(QName('selected'), 'selected')]
                    elif 'selected' in attrs:
                        attrs -= 'selected'
                    yield okind, (tag, attrs), opos
                    if option_text:
                        yield option_text
                    in_option = False
                    option_start = option_text = option_value = None
                elif tagname == 'textarea':
                    if textarea_value:
                        yield TEXT, unicode(textarea_value), pos
                    in_textarea = False
                yield kind, data, pos

            else:
                yield kind, data, pos


class HTMLSanitizer(object):
    """A filter that removes potentially dangerous HTML tags and attributes
    from the stream.
    
    >>> from genshi import HTML
    >>> html = HTML('<div><script>alert(document.cookie)</script></div>')
    >>> print html | HTMLSanitizer()
    <div/>
    
    The default set of safe tags and attributes can be modified when the filter
    is instantiated. For example, to allow inline ``style`` attributes, the
    following instantation would work:
    
    >>> html = HTML('<div style="background: #000"></div>')
    >>> sanitizer = HTMLSanitizer(safe_attrs=HTMLSanitizer.SAFE_ATTRS | set(['style']))
    >>> print html | sanitizer
    <div style="background: #000"/>
    
    Note that even in this case, the filter *does* attempt to remove dangerous
    constructs from style attributes:

    >>> html = HTML('<div style="background: url(javascript:void); color: #000"></div>')
    >>> print html | sanitizer
    <div style="color: #000"/>
    
    This handles HTML entities, unicode escapes in CSS and Javascript text, as
    well as a lot of other things. However, the style tag is still excluded by
    default because it is very hard for such sanitizing to be completely safe,
    especially considering how much error recovery current web browsers perform.
    """

    SAFE_TAGS = frozenset(['a', 'abbr', 'acronym', 'address', 'area', 'b',
        'big', 'blockquote', 'br', 'button', 'caption', 'center', 'cite',
        'code', 'col', 'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt',
        'em', 'fieldset', 'font', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'hr', 'i', 'img', 'input', 'ins', 'kbd', 'label', 'legend', 'li', 'map',
        'menu', 'ol', 'optgroup', 'option', 'p', 'pre', 'q', 's', 'samp',
        'select', 'small', 'span', 'strike', 'strong', 'sub', 'sup', 'table',
        'tbody', 'td', 'textarea', 'tfoot', 'th', 'thead', 'tr', 'tt', 'u',
        'ul', 'var'])

    SAFE_ATTRS = frozenset(['abbr', 'accept', 'accept-charset', 'accesskey',
        'action', 'align', 'alt', 'axis', 'bgcolor', 'border', 'cellpadding',
        'cellspacing', 'char', 'charoff', 'charset', 'checked', 'cite', 'class',
        'clear', 'cols', 'colspan', 'color', 'compact', 'coords', 'datetime',
        'dir', 'disabled', 'enctype', 'for', 'frame', 'headers', 'height',
        'href', 'hreflang', 'hspace', 'id', 'ismap', 'label', 'lang',
        'longdesc', 'maxlength', 'media', 'method', 'multiple', 'name',
        'nohref', 'noshade', 'nowrap', 'prompt', 'readonly', 'rel', 'rev',
        'rows', 'rowspan', 'rules', 'scope', 'selected', 'shape', 'size',
        'span', 'src', 'start', 'summary', 'tabindex', 'target', 'title',
        'type', 'usemap', 'valign', 'value', 'vspace', 'width'])

    SAFE_SCHEMES = frozenset(['file', 'ftp', 'http', 'https', 'mailto', None])

    URI_ATTRS = frozenset(['action', 'background', 'dynsrc', 'href', 'lowsrc',
        'src'])

    def __init__(self, safe_tags=SAFE_TAGS, safe_attrs=SAFE_ATTRS,
                 safe_schemes=SAFE_SCHEMES, uri_attrs=URI_ATTRS):
        """Create the sanitizer.
        
        The exact set of allowed elements and attributes can be configured.
        
        :param safe_tags: a set of tag names that are considered safe
        :param safe_attrs: a set of attribute names that are considered safe
        :param safe_schemes: a set of URI schemes that are considered safe
        :param uri_attrs: a set of names of attributes that contain URIs
        """
        self.safe_tags = safe_tags
        self.safe_attrs = safe_attrs
        self.uri_attrs = uri_attrs
        self.safe_schemes = safe_schemes

    def __call__(self, stream):
        """Apply the filter to the given stream.
        
        :param stream: the markup event stream to filter
        """
        waiting_for = None

        def _get_scheme(href):
            if ':' not in href:
                return None
            chars = [char for char in href.split(':', 1)[0] if char.isalnum()]
            return ''.join(chars).lower()

        for kind, data, pos in stream:
            if kind is START:
                if waiting_for:
                    continue
                tag, attrs = data
                if tag not in self.safe_tags:
                    waiting_for = tag
                    continue

                new_attrs = []
                for attr, value in attrs:
                    value = stripentities(value)
                    if attr not in self.safe_attrs:
                        continue
                    elif attr in self.uri_attrs:
                        # Don't allow URI schemes such as "javascript:"
                        if _get_scheme(value) not in self.safe_schemes:
                            continue
                    elif attr == 'style':
                        # Remove dangerous CSS declarations from inline styles
                        decls = []
                        value = self._replace_unicode_escapes(value)
                        for decl in filter(None, value.split(';')):
                            is_evil = False
                            if 'expression' in decl:
                                is_evil = True
                            for m in re.finditer(r'url\s*\(([^)]+)', decl):
                                if _get_scheme(m.group(1)) not in self.safe_schemes:
                                    is_evil = True
                                    break
                            if not is_evil:
                                decls.append(decl.strip())
                        if not decls:
                            continue
                        value = '; '.join(decls)
                    new_attrs.append((attr, value))

                yield kind, (tag, Attrs(new_attrs)), pos

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

    _NORMALIZE_NEWLINES = re.compile(r'\r\n').sub
    _UNICODE_ESCAPE = re.compile(r'\\([0-9a-fA-F]{1,6})\s?').sub

    def _replace_unicode_escapes(self, text):
        def _repl(match):
            return unichr(int(match.group(1), 16))
        return self._UNICODE_ESCAPE(_repl, self._NORMALIZE_NEWLINES('\n', text))
