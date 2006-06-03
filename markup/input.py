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

from xml.parsers import expat
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import HTMLParser as html
import htmlentitydefs
import re
from StringIO import StringIO

from markup.core import Attributes, Markup, QName, Stream


class XMLParser(object):
    """Generator-based XML parser based on roughly equivalent code in
    Kid/ElementTree."""

    def __init__(self, source):
        self.source = source

        # Setup the Expat parser
        parser = expat.ParserCreate('utf-8', '}')
        parser.buffer_text = True
        parser.returns_unicode = True
        parser.StartElementHandler = self._handle_start
        parser.EndElementHandler = self._handle_end
        parser.CharacterDataHandler = self._handle_data
        parser.XmlDeclHandler = self._handle_prolog
        parser.StartDoctypeDeclHandler = self._handle_doctype
        parser.StartNamespaceDeclHandler = self._handle_start_ns
        parser.EndNamespaceDeclHandler = self._handle_end_ns
        parser.ProcessingInstructionHandler = self._handle_pi
        parser.CommentHandler = self._handle_comment
        parser.DefaultHandler = self._handle_other

        # Location reporting is only support in Python >= 2.4
        if not hasattr(parser, 'CurrentLineNumber'):
            self.getpos = self._getpos_unknown

        self.expat = parser
        self.queue = []

    def __iter__(self):
        bufsize = 4 * 1024 # 4K
        done = False
        while True:
            while not done and len(self.queue) == 0:
                data = self.source.read(bufsize)
                if data == '': # end of data
                    if hasattr(self, 'expat'):
                        self.expat.Parse('', True)
                        del self.expat # get rid of circular references
                    done = True
                else:
                    self.expat.Parse(data, False)
            for event in self.queue:
                yield event
            self.queue = []
            if done:
                break

    def _getpos_unknown(self):
        return (-1, -1)

    def getpos(self):
        return self.expat.CurrentLineNumber, self.expat.CurrentColumnNumber

    def _handle_start(self, tag, attrib):
        self.queue.append((Stream.START, (QName(tag), Attributes(attrib.items())),
                           self.getpos()))

    def _handle_end(self, tag):
        self.queue.append((Stream.END, QName(tag), self.getpos()))

    def _handle_data(self, text):
        self.queue.append((Stream.TEXT, text, self.getpos()))

    def _handle_prolog(self, version, encoding, standalone):
        self.queue.append((Stream.PROLOG, (version, encoding, standalone),
                           self.getpos()))

    def _handle_doctype(self, name, sysid, pubid, has_internal_subset):
        self.queue.append((Stream.DOCTYPE, (name, pubid, sysid), self.getpos()))

    def _handle_start_ns(self, prefix, uri):
        self.queue.append((Stream.START_NS, (prefix or '', uri), self.getpos()))

    def _handle_end_ns(self, prefix):
        self.queue.append((Stream.END_NS, prefix or '', self.getpos()))

    def _handle_pi(self, target, data):
        self.queue.append((Stream.PI, (target, data), self.getpos()))

    def _handle_comment(self, text):
        self.queue.append((Stream.COMMENT, text, self.getpos()))

    def _handle_other(self, text):
        if text.startswith('&'):
            # deal with undefined entities
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
                self.queue.append((Stream.TEXT, text, self.getpos()))
            except KeyError:
                lineno, offset = self.getpos()
                raise expat.error("undefined entity %s: line %d, column %d" %
                                  (text, lineno, offset))


def XML(text):
    return Stream(list(XMLParser(StringIO(text))))


class HTMLParser(html.HTMLParser):
    """Parser for HTML input based on the Python `HTMLParser` module.
    
    This class provides the same interface for generating stream events as
    `XMLParser`, and attempts to automatically balance tags.
    """

    _EMPTY_ELEMS = frozenset(['area', 'base', 'basefont', 'br', 'col', 'frame',
                              'hr', 'img', 'input', 'isindex', 'link', 'meta',
                              'param'])

    def __init__(self, source):
        html.HTMLParser.__init__(self)
        self.source = source
        self.queue = []
        self._open_tags = []

    def __iter__(self):
        bufsize = 4 * 1024 # 4K
        done = False
        while True:
            while not done and len(self.queue) == 0:
                data = self.source.read(bufsize)
                if data == '': # end of data
                    self.close()
                    done = True
                else:
                    self.feed(data)
            for kind, data, pos in self.queue:
                yield kind, data, pos
            self.queue = []
            if done:
                open_tags = self._open_tags
                open_tags.reverse()
                for tag in open_tags:
                    yield Stream.END, QName(tag), pos
                break

    def handle_starttag(self, tag, attrib):
        pos = self.getpos()
        self.queue.append((Stream.START, (QName(tag), Attributes(attrib)), pos))
        if tag in self._EMPTY_ELEMS:
            self.queue.append((Stream.END, QName(tag), pos))
        else:
            self._open_tags.append(tag)

    def handle_endtag(self, tag):
        if tag not in self._EMPTY_ELEMS:
            pos = self.getpos()
            while self._open_tags:
                open_tag = self._open_tags.pop()
                if open_tag.lower() == tag.lower():
                    break
                self.queue.append((Stream.END, QName(open_tag), pos))
            self.queue.append((Stream.END, QName(tag), pos))

    def handle_data(self, text):
        self.queue.append((Stream.TEXT, text, self.getpos()))

    def handle_charref(self, name):
        self.queue.append((Stream.TEXT, Markup('&#%s;' % name), self.getpos()))

    def handle_entityref(self, name):
        self.queue.append((Stream.TEXT, Markup('&%s;' % name), self.getpos()))

    def handle_pi(self, data):
        target, data = data.split(maxsplit=1)
        data = data.rstrip('?')
        self.queue.append((Stream.PI, (target.strip(), data.strip()),
                           self.getpos()))

    def handle_comment(self, text):
        self.queue.append((Stream.COMMENT, text, self.getpos()))


def HTML(text):
    return Stream(list(HTMLParser(StringIO(text))))
