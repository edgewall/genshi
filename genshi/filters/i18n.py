"""Utilities for internationalization and localization of templates."""

try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
from gettext import gettext
from opcode import opmap
import re

from genshi.core import Attrs, Namespace, QName, START, END, TEXT, _ensure
from genshi.template.base import Template, EXPR, SUB
from genshi.template.markup import EXEC

_LOAD_NAME = chr(opmap['LOAD_NAME'])
_LOAD_CONST = chr(opmap['LOAD_CONST'])
_CALL_FUNCTION = chr(opmap['CALL_FUNCTION'])
_BINARY_ADD = chr(opmap['BINARY_ADD'])


class Translator(object):
    """Can extract and translate localizable strings from markup streams and
    templates.
    
    For example, assume the followng template:
    
    >>> from genshi.template import MarkupTemplate
    >>> 
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
    >>> 
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

    IGNORE_TAGS = frozenset([
        QName('script'), QName('http://www.w3.org/1999/xhtml}script'),
        QName('style'), QName('http://www.w3.org/1999/xhtml}style')
    ])
    INCLUDE_ATTRS = frozenset(['abbr', 'alt', 'label', 'prompt', 'standby',
                               'summary', 'title'])

    def __init__(self, translate=gettext, ignore_tags=IGNORE_TAGS,
                 include_attrs=INCLUDE_ATTRS):
        """Initialize the translator.
        
        :param translate: the translation function, for example ``gettext`` or
                          ``ugettext``.
        :param ignore_tags: a set of tag names that should not be localized
        :param include_attrs: a set of attribute names should be localized
        """
        self.translate = translate
        self.ignore_tags = ignore_tags
        self.include_attrs = include_attrs

    def __call__(self, stream, ctxt=None, search_text=True):
        """Translate any localizable strings in the given stream.
        
        This function shouldn't be called directly. Instead, an instance of
        the `Translator` class should be registered as a filter with the
        `Template` or the `TemplateLoader`, or applied as a regular stream
        filter. If used as a template filter, it should be inserted in front of
        all the default filters.
        
        :param stream: the markup event stream
        :param ctxt: the template context (not used)
        :param search_text: whether text nodes should be translated (used
                            internally)
        :return: the localized stream
        """
        ignore_tags = self.ignore_tags
        include_attrs = self.include_attrs
        translate = self.translate
        skip = 0

        for kind, data, pos in stream:

            # skip chunks that should not be localized
            if skip:
                if kind is START:
                    tag, attrs = data
                    if tag in ignore_tags:
                        skip += 1
                elif kind is END:
                    if tag in ignore_tags:
                        skip -= 1
                yield kind, data, pos
                continue

            # handle different events that can be localized
            if kind is START:
                tag, attrs = data
                if tag in ignore_tags:
                    skip += 1
                    yield kind, data, pos
                    continue

                new_attrs = []
                changed = False
                for name, value in attrs:
                    newval = value
                    if isinstance(value, basestring):
                        if name in include_attrs:
                            newval = self.translate(value)
                    else:
                        newval = list(self(_ensure(value), ctxt,
                            search_text=name in include_attrs)
                        )
                    if newval != value:
                        value = newval
                        changed = True
                    new_attrs.append((name, value))
                if changed:
                    attrs = new_attrs

                yield kind, (tag, attrs), pos

            elif search_text and kind is TEXT:
                text = data.strip()
                if text:
                    data = data.replace(text, translate(text))
                yield kind, data, pos

            elif kind is SUB:
                subkind, substream = data
                new_substream = list(self(substream, ctxt))
                yield kind, (subkind, new_substream), pos

            else:
                yield kind, data, pos

    GETTEXT_FUNCTIONS = ('_', 'gettext', 'ngettext', 'dgettext', 'dngettext',
                         'ugettext', 'ungettext')

    def extract(self, stream, gettext_functions=GETTEXT_FUNCTIONS,
                search_text=True):
        """Extract localizable strings from the given template stream.
        
        For every string found, this function yields a ``(lineno, function,
        message)`` tuple, where:
        
        * ``lineno`` is the number of the line on which the string was found,
        * ``function`` is the name of the ``gettext`` function used (if the
          string was extracted from embedded Python code), and
        *  ``message`` is the string itself (a ``unicode`` object, or a tuple
           of ``unicode`` objects for functions with multiple string arguments).
        
        >>> from genshi.template import MarkupTemplate
        >>> 
        >>> tmpl = MarkupTemplate('''<html xmlns:py="http://genshi.edgewall.org/">
        ...   <head>
        ...     <title>Example</title>
        ...   </head>
        ...   <body>
        ...     <h1>Example</h1>
        ...     <p>${_("Hello, %(name)s") % dict(name=username)}</p>
        ...     <p>${ngettext("You have %d item", "You have %d items", num)}</p>
        ...   </body>
        ... </html>''', filename='example.html')
        >>> 
        >>> for lineno, funcname, message in Translator().extract(tmpl.stream):
        ...    print "%d, %r, %r" % (lineno, funcname, message)
        3, None, u'Example'
        6, None, u'Example'
        7, '_', u'Hello, %(name)s'
        8, 'ngettext', (u'You have %d item', u'You have %d items')
        
        :param stream: the event stream to extract strings from; can be a
                       regular stream or a template stream
        :param gettext_functions: a sequence of function names that should be
                                  treated as gettext-style localization
                                  functions
        :param search_text: whether the content of text nodes should be
                            extracted (used internally)
        
        :note: Changed in 0.4.1: For a function with multiple string arguments
               (such as ``ngettext``), a single item with a tuple of strings is
               yielded, instead an item for each string argument.
        """
        tagname = None
        skip = 0

        for kind, data, pos in stream:
            if skip:
                if kind is START:
                    tag, attrs = data
                    if tag in self.ignore_tags:
                        skip += 1
                if kind is END:
                    tag = data
                    if tag in self.ignore_tags:
                        skip -= 1
                continue

            if kind is START:
                tag, attrs = data
                if tag in self.ignore_tags:
                    skip += 1
                    continue

                for name, value in attrs:
                    if isinstance(value, basestring):
                        if name in self.include_attrs:
                            text = value.strip()
                            if text:
                                yield pos[1], None, text
                    else:
                        for lineno, funcname, text in self.extract(
                                _ensure(value), gettext_functions,
                                search_text=name in self.include_attrs):
                            yield lineno, funcname, text

            elif search_text and kind is TEXT:
                text = data.strip()
                if text and filter(None, [ch.isalpha() for ch in text]):
                    yield pos[1], None, text

            elif kind is EXPR or kind is EXEC:
                consts = dict([(n, chr(i) + '\x00') for i, n in
                               enumerate(data.code.co_consts)])
                gettext_locs = [consts[n] for n in gettext_functions
                                if n in consts]
                ops = [
                    _LOAD_CONST, '(', '|'.join(gettext_locs), ')',
                    _CALL_FUNCTION, '.\x00',
                    '((?:', _BINARY_ADD, '|', _LOAD_CONST, '.\x00)+)'
                ]
                for loc, opcodes in re.findall(''.join(ops), data.code.co_code):
                    funcname = data.code.co_consts[ord(loc[0])]
                    strings = []
                    opcodes = iter(opcodes)
                    for opcode in opcodes:
                        if opcode == _BINARY_ADD:
                            arg = strings.pop()
                            strings[-1] += arg
                        else:
                            arg = data.code.co_consts[ord(opcodes.next())]
                            opcodes.next() # skip second byte
                            if not isinstance(arg, basestring):
                                break
                            strings.append(unicode(arg))
                    if len(strings) == 1:
                        strings = strings[0]
                    else:
                        strings = tuple(strings)
                    yield pos[1], funcname, strings

            elif kind is SUB:
                subkind, substream = data
                for lineno, funcname, text in self.extract(substream,
                                                           gettext_functions):
                    yield lineno, funcname, text
