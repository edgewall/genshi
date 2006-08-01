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
import unittest

from markup.core import *
from markup.input import ParseError


class MarkupTestCase(unittest.TestCase):

    def test_repr(self):
        markup = Markup('foo')
        self.assertEquals('<Markup "foo">', repr(markup))

    def test_escape(self):
        markup = escape('<b>"&"</b>')
        assert isinstance(markup, Markup)
        self.assertEquals('&lt;b&gt;&#34;&amp;&#34;&lt;/b&gt;', markup)

    def test_escape_noquotes(self):
        markup = escape('<b>"&"</b>', quotes=False)
        assert isinstance(markup, Markup)
        self.assertEquals('&lt;b&gt;"&amp;"&lt;/b&gt;', markup)

    def test_unescape_markup(self):
        string = '<b>"&"</b>'
        markup = Markup.escape(string)
        assert isinstance(markup, Markup)
        self.assertEquals(string, unescape(markup))

    def test_add_str(self):
        markup = Markup('<b>foo</b>') + '<br/>'
        assert isinstance(markup, Markup)
        self.assertEquals('<b>foo</b>&lt;br/&gt;', markup)

    def test_add_markup(self):
        markup = Markup('<b>foo</b>') + Markup('<br/>')
        assert isinstance(markup, Markup)
        self.assertEquals('<b>foo</b><br/>', markup)

    def test_add_reverse(self):
        markup = 'foo' + Markup('<b>bar</b>')
        assert isinstance(markup, unicode)
        self.assertEquals('foo<b>bar</b>', markup)

    def test_mod(self):
        markup = Markup('<b>%s</b>') % '&'
        assert isinstance(markup, Markup)
        self.assertEquals('<b>&amp;</b>', markup)

    def test_mod_multi(self):
        markup = Markup('<b>%s</b> %s') % ('&', 'boo')
        assert isinstance(markup, Markup)
        self.assertEquals('<b>&amp;</b> boo', markup)

    def test_mul(self):
        markup = Markup('<b>foo</b>') * 2
        assert isinstance(markup, Markup)
        self.assertEquals('<b>foo</b><b>foo</b>', markup)

    def test_join(self):
        markup = Markup('<br />').join(['foo', '<bar />', Markup('<baz />')])
        assert isinstance(markup, Markup)
        self.assertEquals('foo<br />&lt;bar /&gt;<br /><baz />', markup)

    def test_stripentities_all(self):
        markup = Markup('&amp; &#106;').stripentities()
        assert isinstance(markup, Markup)
        self.assertEquals('& j', markup)

    def test_stripentities_keepxml(self):
        markup = Markup('&amp; &#106;').stripentities(keepxmlentities=True)
        assert isinstance(markup, Markup)
        self.assertEquals('&amp; j', markup)

    def test_striptags_empty(self):
        markup = Markup('<br />').striptags()
        assert isinstance(markup, Markup)
        self.assertEquals('', markup)

    def test_striptags_mid(self):
        markup = Markup('<a href="#">fo<br />o</a>').striptags()
        assert isinstance(markup, Markup)
        self.assertEquals('foo', markup)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MarkupTestCase, 'test'))
    suite.addTest(doctest.DocTestSuite(Markup.__module__))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
