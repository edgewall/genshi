"""Utilities for internationalization and localization of templates."""

try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
from gettext import gettext
from opcode import opmap
import re

from genshi.core import Attrs, START, END, TEXT
from genshi.template.base import Template, EXPR, SUB
from genshi.template.markup import EXEC

LOAD_NAME = chr(opmap['LOAD_NAME'])
LOAD_CONST = chr(opmap['LOAD_CONST'])
CALL_FUNCTION = chr(opmap['CALL_FUNCTION'])
BINARY_ADD = chr(opmap['BINARY_ADD'])


class Translator(object):
    """Can extract and translate localizable strings from markup streams and
    templates
    
    For example, assume the followng template:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<html xmlns:py="http://genshi.edgewall.org/">
    ...   <head>
    ...     <title>Example</title>
    ...   </head>
    ...   <body>
    ...     <h1>Example</h1>
    ...     <p>${_("Hello, %(name)s") % dict(name=username)}</p>
    ...   </body>
    ... </html>''', filename='example.html')
    
    For demonstration, we define a dummy ``gettext``-style function with a
    hard-coded translation table, and pass that to the `Translator` initializer:
    
    >>> def pseudo_gettext(string):
    ...     return {
    ...         'Example': 'Beispiel',
    ...         'Hello, %(name)s': 'Hallo, %(name)s'
    ...     }[string]
    >>> translator = Translator(pseudo_gettext)
    
    Next, the translator needs to be prepended to any already defined filters
    on the template:
    
    >>> tmpl.filters.insert(0, translator)
    
    When generating the template output, our hard-coded translations should be
    applied as expected:
    
    >>> print tmpl.generate(username='Hans', _=pseudo_gettext)
    <html>
      <head>
        <title>Beispiel</title>
      </head>
      <body>
        <h1>Beispiel</h1>
        <p>Hallo, Hans</p>
      </body>
    </html>
    """

    IGNORE_TAGS = frozenset(['script', 'style'])
    INCLUDE_ATTRS = frozenset(['title', 'alt'])

    def __init__(self, translate=gettext, ignore_tags=IGNORE_TAGS,
                 include_attrs=INCLUDE_ATTRS):
        """Initialize the translator.
        
        :param translate: the translation function, for example ``gettext`` or
                          ``ugettext``.
        :param ignore_tags: a set of tag names that should not be localized
        :param include_attrs: a set of attribute names should be localized
        """
        self.gettext = translate
        self.ignore_tags = ignore_tags
        self.include_attrs = include_attrs

    def __call__(self, stream, ctxt=None, search_text=True):
        skip = 0

        for kind, data, pos in stream:

            # skip chunks that should not be localized
            if skip:
                if kind is START:
                    tag, attrs = data
                    tag = tag.localname
                    if tag.localname in self.ignore_tags:
                        skip += 1
                elif kind is END:
                    if tag.localname in self.ignore_tags:
                        skip -= 1
                yield kind, data, pos
                continue

            # handle different events that can be localized
            if kind is START:
                tag, attrs = data
                if tag.localname in self.ignore_tags:
                    skip += 1
                    yield kind, data, pos
                    continue

                new_attrs = list(attrs)
                changed = False
                for name, value in attrs:
                    if name in include_attrs:
                        if isinstance(value, basestring):
                            newval = ugettext(value)
                        else:
                            newval = list(self(value, ctxt, search_text=name in self.include_attrs))
                        if newval != value:
                            value = new_val
                            changed = True
                    new_attrs.append((name, value))
                if changed:
                    attrs = new_attrs

                yield kind, (tag, attrs), pos

            elif kind is TEXT:
                text = data.strip()
                if text:
                    data = data.replace(text, self.gettext(text))
                yield kind, data, pos

            elif kind is SUB:
                subkind, substream = data
                new_substream = list(self(substream, ctxt))
                yield kind, (subkind, new_substream), pos

            else:
                yield kind, data, pos

    def extract(self, stream, gettext_functions=('_', 'gettext', 'ngettext')):
        """Extract localizable strings from the given template stream.
        
        For every string found, this function yields a ``(lineno, message)``
        tuple.
        
        :param stream: the event stream to extract strings from; can be a
                       regular stream or a template stream
        
        >>> from genshi.template import MarkupTemplate
        >>> tmpl = MarkupTemplate('''<html xmlns:py="http://genshi.edgewall.org/">
        ...   <head>
        ...     <title>Example</title>
        ...   </head>
        ...   <body>
        ...     <h1>Example</h1>
        ...     <p>${_("Hello, %(name)s") % dict(name=username)}</p>
        ...   </body>
        ... </html>''', filename='example.html')
        >>> for lineno, message in Translator().extract(tmpl.stream):
        ...    print "Line %d: %r" % (lineno, message)
        Line 3: u'Example'
        Line 6: u'Example'
        Line 7: u'Hello, %(name)s'
        """
        tagname = None
        skip = 0

        for kind, data, pos in stream:
            if skip:
                if kind is START:
                    tag, attrs = data
                    if tag.localname in self.ignore_tags:
                        skip += 1
                if kind is END:
                    tag = data
                    if tag.localname in self.ignore_tags:
                        skip -= 1
                continue

            if kind is START:
                tag, attrs = data
                if tag.localname in self.ignore_tags:
                    skip += 1
                    continue

                for name, value in attrs:
                    if name in self.include_attrs:
                        if isinstance(value, basestring):
                            text = value.strip()
                            if text:
                                yield pos[1], text
                        else:
                            for lineno, text in harvest(value):
                                yield lineno, text

            elif kind is TEXT:
                text = data.strip()
                if text and filter(None, [ch.isalpha() for ch in text]):
                    yield pos[1], text

            elif kind is EXPR or kind is EXEC:
                consts = dict([(n, chr(i) + '\x00') for i, n in
                               enumerate(data.code.co_consts)])
                gettext_locs = [consts[n] for n in gettext_functions
                                if n in consts]
                ops = [
                    LOAD_CONST, '(', '|'.join(gettext_locs), ')',
                    CALL_FUNCTION, '.\x00',
                    '((?:', BINARY_ADD, '|', LOAD_CONST, '.\x00)+)'
                ]
                for _, opcodes in re.findall(''.join(ops), data.code.co_code):
                    strings = []
                    opcodes = iter(opcodes)
                    for opcode in opcodes:
                        if opcode == BINARY_ADD:
                            arg = strings.pop()
                            strings[-1] += arg
                        else:
                            arg = data.code.co_consts[ord(opcodes.next())]
                            opcodes.next() # skip second byte
                            if not isinstance(arg, basestring):
                                break
                            strings.append(unicode(arg))
                    for string in strings:
                        yield pos[1], string

            elif kind is SUB:
                subkind, substream = data
                for lineno, text in self.harvest(substream):
                    yield lineno, text
