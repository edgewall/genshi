# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://markup.cmlenz.net/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://markup.cmlenz.net/log/.

import doctest
import unittest
import sys

from markup.core import Stream
from markup.template import BadDirectiveError, Context, Template, \
                            TemplateSyntaxError


class MatchDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:match` template directive."""

    def test_without_strip(self):
        """
        Verify that a match template can produce the same kind of element that
        it matched without entering an infinite recursion.
        """
        tmpl = Template("""<doc xmlns:py="http://purl.org/kid/ns#">
          <elem py:match="elem">
            <div class="elem">${select('*/text()')}</div>
          </elem>
          <elem>Hey Joe</elem>
        </doc>""")
        self.assertEqual("""<doc>
          <elem>
            <div class="elem">Hey Joe</div>
          </elem>
        </doc>""", str(tmpl.generate()))

    def test_recursive_match_1(self):
        """
        Match directives are applied recursively, meaning that they are also
        applied to any content they may have produced themselves:
        """
        tmpl = Template("""<doc xmlns:py="http://purl.org/kid/ns#">
          <elem py:match="elem">
            <div class="elem">
              ${select('*/*')}
            </div>
          </elem>
          <elem>
            <subelem>
              <elem/>
            </subelem>
          </elem>
        </doc>""")
        self.assertEqual("""<doc>
          <elem>
            <div class="elem">
              <subelem>
              <elem>
            <div class="elem">
            </div>
          </elem>
            </subelem>
            </div>
          </elem>
        </doc>""", str(tmpl.generate()))

    def test_recursive_match_2(self):
        """
        When two or more match templates match the same element and also
        themselves output the element they match, avoiding recursion is even
        more complex, but should work.
        """
        tmpl = Template("""<html xmlns:py="http://purl.org/kid/ns#">
          <body py:match="body">
            <div id="header"/>
            ${select('*/*')}
          </body>
          <body py:match="body">
            ${select('*/*')}
            <div id="footer"/>
          </body>
          <body>
            <h1>Foo</h1>
          </body>
        </html>""")
        self.assertEqual("""<html>
          <body>
            <div id="header"/><h1>Foo</h1>
            <div id="footer"/>
          </body>
        </html>""", str(tmpl.generate()))


class StripDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:strip` template directive."""

    def test_strip_false(self):
        tmpl = Template("""<div xmlns:py="http://purl.org/kid/ns#">
          <div py:strip="False"><b>foo</b></div>
        </div>""")
        self.assertEqual("""<div>
          <div><b>foo</b></div>
        </div>""", str(tmpl.generate()))

    def test_strip_empty(self):
        tmpl = Template("""<div xmlns:py="http://purl.org/kid/ns#">
          <div py:strip=""><b>foo</b></div>
        </div>""")
        self.assertEqual("""<div>
          <b>foo</b>
        </div>""", str(tmpl.generate()))


class TemplateTestCase(unittest.TestCase):
    """Tests for basic template processing, expression evaluation and error
    reporting.
    """

    def test_interpolate_string(self):
        parts = list(Template._interpolate('bla'))
        self.assertEqual(1, len(parts))
        self.assertEqual(Stream.TEXT, parts[0][0])
        self.assertEqual('bla', parts[0][1])

    def test_interpolate_simple(self):
        parts = list(Template._interpolate('${bla}'))
        self.assertEqual(1, len(parts))
        self.assertEqual(Template.EXPR, parts[0][0])
        self.assertEqual('bla', parts[0][1].source)

    def test_interpolate_escaped(self):
        parts = list(Template._interpolate('$${bla}'))
        self.assertEqual(1, len(parts))
        self.assertEqual(Stream.TEXT, parts[0][0])
        self.assertEqual('${bla}', parts[0][1])

    def test_interpolate_short(self):
        parts = list(Template._interpolate('$bla'))
        self.assertEqual(1, len(parts))
        self.assertEqual(Template.EXPR, parts[0][0])
        self.assertEqual('bla', parts[0][1].source)

    def test_interpolate_mixed1(self):
        parts = list(Template._interpolate('$foo bar $baz'))
        self.assertEqual(3, len(parts))
        self.assertEqual(Template.EXPR, parts[0][0])
        self.assertEqual('foo', parts[0][1].source)
        self.assertEqual(Stream.TEXT, parts[1][0])
        self.assertEqual(' bar ', parts[1][1])
        self.assertEqual(Template.EXPR, parts[2][0])
        self.assertEqual('baz', parts[2][1].source)

    def test_interpolate_mixed2(self):
        parts = list(Template._interpolate('foo $bar baz'))
        self.assertEqual(3, len(parts))
        self.assertEqual(Stream.TEXT, parts[0][0])
        self.assertEqual('foo ', parts[0][1])
        self.assertEqual(Template.EXPR, parts[1][0])
        self.assertEqual('bar', parts[1][1].source)
        self.assertEqual(Stream.TEXT, parts[2][0])
        self.assertEqual(' baz', parts[2][1])

    def test_bad_directive_error(self):
        xml = '<p xmlns:py="http://purl.org/kid/ns#" py:do="nothing" />'
        try:
            tmpl = Template(xml, filename='test.html')
        except BadDirectiveError, e:
            self.assertEqual('test.html', e.filename)
            if sys.version_info[:2] >= (2, 4):
                self.assertEqual(1, e.lineno)

    def test_directive_value_syntax_error(self):
        xml = '<p xmlns:py="http://purl.org/kid/ns#" py:if="bar\'" />'
        tmpl = Template(xml, filename='test.html')
        try:
            list(tmpl.generate(Context()))
            self.fail('Expected SyntaxError')
        except TemplateSyntaxError, e:
            self.assertEqual('test.html', e.filename)
            if sys.version_info[:2] >= (2, 4):
                self.assertEqual(1, e.lineno)
                # We don't really care about the offset here, do we?

    def test_expression_syntax_error(self):
        xml = '<p>\n  Foo <em>${bar"}</em>\n</p>'
        tmpl = Template(xml, filename='test.html')
        ctxt = Context(bar='baz')
        try:
            list(tmpl.generate(ctxt))
            self.fail('Expected SyntaxError')
        except TemplateSyntaxError, e:
            self.assertEqual('test.html', e.filename)
            if sys.version_info[:2] >= (2, 4):
                self.assertEqual(2, e.lineno)
                self.assertEqual(10, e.offset)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(Template.__module__))
    suite.addTest(unittest.makeSuite(TemplateTestCase, 'test'))
    suite.addTest(unittest.makeSuite(MatchDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(StripDirectiveTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
