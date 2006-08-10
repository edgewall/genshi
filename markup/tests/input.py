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

import doctest
from StringIO import StringIO
import sys
import unittest

from markup.core import Stream
from markup.input import XMLParser, HTMLParser


class XMLParserTestCase(unittest.TestCase):

    def test_text_node_pos_single_line(self):
        text = '<elem>foo bar</elem>'
        events = list(XMLParser(StringIO(text)))
        kind, data, pos = events[1]
        self.assertEqual(Stream.TEXT, kind)
        self.assertEqual(u'foo bar', data)
        if sys.version_info[:2] >= (2, 4):
            self.assertEqual((None, 1, 6), pos)

    def test_text_node_pos_multi_line(self):
        text = '''<elem>foo
bar</elem>'''
        events = list(XMLParser(StringIO(text)))
        kind, data, pos = events[1]
        self.assertEqual(Stream.TEXT, kind)
        self.assertEqual(u'foo\nbar', data)
        if sys.version_info[:2] >= (2, 4):
            self.assertEqual((None, 1, -1), pos)


class HTMLParserTestCase(unittest.TestCase):

    def test_text_node_pos_single_line(self):
        text = '<elem>foo bar</elem>'
        events = list(HTMLParser(StringIO(text)))
        kind, data, pos = events[1]
        self.assertEqual(Stream.TEXT, kind)
        self.assertEqual(u'foo bar', data)
        if sys.version_info[:2] >= (2, 4):
            self.assertEqual((None, 1, 6), pos)

    def test_text_node_pos_multi_line(self):
        text = '''<elem>foo
bar</elem>'''
        events = list(HTMLParser(StringIO(text)))
        kind, data, pos = events[1]
        self.assertEqual(Stream.TEXT, kind)
        self.assertEqual(u'foo\nbar', data)
        if sys.version_info[:2] >= (2, 4):
            self.assertEqual((None, 1, 6), pos)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(XMLParser.__module__))
    suite.addTest(unittest.makeSuite(XMLParserTestCase, 'test'))
    suite.addTest(unittest.makeSuite(HTMLParserTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
