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

import doctest
import os
import shutil
import tempfile
import unittest

from genshi.core import Stream
from genshi.input import HTML, ParseError
from genshi.filters import HTMLSanitizer
from genshi.template import TemplateLoader


class HTMLSanitizerTestCase(unittest.TestCase):

    def test_sanitize_unchanged(self):
        html = HTML('<a href="#">fo<br />o</a>')
        self.assertEquals(u'<a href="#">fo<br/>o</a>',
                          unicode(html | HTMLSanitizer()))

    def test_sanitize_escape_text(self):
        html = HTML('<a href="#">fo&amp;</a>')
        self.assertEquals(u'<a href="#">fo&amp;</a>',
                          unicode(html | HTMLSanitizer()))
        html = HTML('<a href="#">&lt;foo&gt;</a>')
        self.assertEquals(u'<a href="#">&lt;foo&gt;</a>',
                          unicode(html | HTMLSanitizer()))

    def test_sanitize_entityref_text(self):
        html = HTML('<a href="#">fo&ouml;</a>')
        self.assertEquals(u'<a href="#">foö</a>',
                          unicode(html | HTMLSanitizer()))

    def test_sanitize_escape_attr(self):
        html = HTML('<div title="&lt;foo&gt;"></div>')
        self.assertEquals(u'<div title="&lt;foo&gt;"/>',
                          unicode(html | HTMLSanitizer()))

    def test_sanitize_close_empty_tag(self):
        html = HTML('<a href="#">fo<br>o</a>')
        self.assertEquals(u'<a href="#">fo<br/>o</a>',
                          unicode(html | HTMLSanitizer()))

    def test_sanitize_invalid_entity(self):
        html = HTML('&junk;')
        self.assertEquals('&amp;junk;', unicode(html | HTMLSanitizer()))

    def test_sanitize_remove_script_elem(self):
        html = HTML('<script>alert("Foo")</script>')
        self.assertEquals(u'', unicode(html | HTMLSanitizer()))
        html = HTML('<SCRIPT SRC="http://example.com/"></SCRIPT>')
        self.assertEquals(u'', unicode(html | HTMLSanitizer()))
        self.assertRaises(ParseError, HTML, '<SCR\0IPT>alert("foo")</SCR\0IPT>')
        self.assertRaises(ParseError, HTML,
                          '<SCRIPT&XYZ SRC="http://example.com/"></SCRIPT>')

    def test_sanitize_remove_onclick_attr(self):
        html = HTML('<div onclick=\'alert("foo")\' />')
        self.assertEquals(u'<div/>', unicode(html | HTMLSanitizer()))

    def test_sanitize_remove_style_scripts(self):
        # Inline style with url() using javascript: scheme
        html = HTML('<DIV STYLE=\'background: url(javascript:alert("foo"))\'>')
        self.assertEquals(u'<div/>', unicode(html | HTMLSanitizer()))
        # Inline style with url() using javascript: scheme, using control char
        html = HTML('<DIV STYLE=\'background: url(&#1;javascript:alert("foo"))\'>')
        self.assertEquals(u'<div/>', unicode(html | HTMLSanitizer()))
        # Inline style with url() using javascript: scheme, in quotes
        html = HTML('<DIV STYLE=\'background: url("javascript:alert(foo)")\'>')
        self.assertEquals(u'<div/>', unicode(html | HTMLSanitizer()))
        # IE expressions in CSS not allowed
        html = HTML('<DIV STYLE=\'width: expression(alert("foo"));\'>')
        self.assertEquals(u'<div/>', unicode(html | HTMLSanitizer()))
        html = HTML('<DIV STYLE=\'background: url(javascript:alert("foo"));'
                                 'color: #fff\'>')
        self.assertEquals(u'<div style="color: #fff"/>',
                          unicode(html | HTMLSanitizer()))

    def test_sanitize_remove_src_javascript(self):
        html = HTML('<img src=\'javascript:alert("foo")\'>')
        self.assertEquals(u'<img/>', unicode(html | HTMLSanitizer()))
        # Case-insensitive protocol matching
        html = HTML('<IMG SRC=\'JaVaScRiPt:alert("foo")\'>')
        self.assertEquals(u'<img/>', unicode(html | HTMLSanitizer()))
        # Grave accents (not parsed)
        self.assertRaises(ParseError, HTML,
                          '<IMG SRC=`javascript:alert("RSnake says, \'foo\'")`>')
        # Protocol encoded using UTF-8 numeric entities
        html = HTML('<IMG SRC=\'&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;'
                    '&#112;&#116;&#58;alert("foo")\'>')
        self.assertEquals(u'<img/>', unicode(html | HTMLSanitizer()))
        # Protocol encoded using UTF-8 numeric entities without a semicolon
        # (which is allowed because the max number of digits is used)
        html = HTML('<IMG SRC=\'&#0000106&#0000097&#0000118&#0000097'
                    '&#0000115&#0000099&#0000114&#0000105&#0000112&#0000116'
                    '&#0000058alert("foo")\'>')
        self.assertEquals(u'<img/>', unicode(html | HTMLSanitizer()))
        # Protocol encoded using UTF-8 numeric hex entities without a semicolon
        # (which is allowed because the max number of digits is used)
        html = HTML('<IMG SRC=\'&#x6A&#x61&#x76&#x61&#x73&#x63&#x72&#x69'
                    '&#x70&#x74&#x3A;alert("foo")\'>')
        self.assertEquals(u'<img/>', unicode(html | HTMLSanitizer()))
        # Embedded tab character in protocol
        html = HTML('<IMG SRC=\'jav\tascript:alert("foo");\'>')
        self.assertEquals(u'<img/>', unicode(html | HTMLSanitizer()))
        # Embedded tab character in protocol, but encoded this time
        html = HTML('<IMG SRC=\'jav&#x09;ascript:alert("foo");\'>')
        self.assertEquals(u'<img/>', unicode(html | HTMLSanitizer()))


class IncludeFilterTestCase(unittest.TestCase):

    def setUp(self):
        self.dirname = tempfile.mkdtemp(suffix='markup_test')

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_select_inluded_elements(self):
        file1 = open(os.path.join(self.dirname, 'tmpl1.html'), 'w')
        try:
            file1.write("""<li>$item</li>""")
        finally:
            file1.close()

        file2 = open(os.path.join(self.dirname, 'tmpl2.html'), 'w')
        try:
            file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude"
                                 xmlns:py="http://genshi.edgewall.org/">
              <ul py:match="ul">${select('li')}</ul>
              <ul py:with="items=(1, 2, 3)">
                <xi:include href="tmpl1.html" py:for="item in items" />
              </ul>
            </html>""")
        finally:
            file2.close()

        loader = TemplateLoader([self.dirname])
        tmpl = loader.load('tmpl2.html')
        self.assertEqual("""<html>
              <ul><li>1</li><li>2</li><li>3</li></ul>
            </html>""", tmpl.generate().render())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(HTMLSanitizerTestCase, 'test'))
    suite.addTest(unittest.makeSuite(IncludeFilterTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
