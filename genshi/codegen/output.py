"""output filters that apply to inline-generated streams"""
from itertools import chain
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import re

from genshi.codegen import adapters
from genshi.core import escape, Markup, Namespace, QName, StreamEventKind
from genshi.core import DOCTYPE, START, END, START_NS, TEXT, START_CDATA, \
                        END_CDATA, PI, COMMENT, XML_NAMESPACE


class PostWhitespaceFilter(object):
    """A filter that removes extraneous ignorable white space from the
    stream."""

    def __init__(self, preserve=None, noescape=None):
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

    def __call__(self, stream, space=XML_NAMESPACE['space'],
                 trim_trailing_space=re.compile('[ \t]+(?=\n)').sub,
                 collapse_lines=re.compile('\n{2,}').sub):
        mjoin = Markup('').join
        preserve_elems = self.preserve
        preserve = False
        noescape_elems = self.noescape
        noescape = False

        textbuf = []
        push_text = textbuf.append
        pop_text = textbuf.pop
        for kind, data, pos, literal in chain(stream, [(None, None, None, None)]):
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
                    yield TEXT, Markup(text), pos, unicode(text)

                if kind is START:
                    namespace, localname, attrib = data
                    tag = (namespace, localname)
                    if not preserve and (tag in preserve_elems or
                                         adapters.get_attrib(attrib, space) == 'preserve'):
                        preserve = True
                    if not noescape and tag in noescape_elems:
                        noescape = True

                elif kind is END:
                    preserve = noescape = False

                elif kind is START_CDATA:
                    noescape = True

                elif kind is END_CDATA:
                    noescape = False

                if kind:
                    yield kind, data, pos, literal
