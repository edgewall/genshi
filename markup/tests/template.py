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


class AttrsDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:attrs` template directive."""

    def test_combined_with_loop(self):
        """
        Verify that the directive has access to the loop variables.
        """
        tmpl = Template("""<doc xmlns:py="http://purl.org/kid/ns#">
          <elem py:for="item in items" py:attrs="item"/>
        </doc>""")
        items = [{'id': 1, 'class': 'foo'}, {'id': 2, 'class': 'bar'}]
        self.assertEqual("""<doc>
          <elem id="1" class="foo"/><elem id="2" class="bar"/>
        </doc>""", str(tmpl.generate(Context(items=items))))


class ChooseDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:choose` template directive and the complementary
    directives `py:when` and `py:otherwise`."""

    def test_multiple_true_whens(self):
        """
        Verify that, if multiple `py:when` bodies match, only the first is
        output.
        """
        tmpl = Template("""<div xmlns:py="http://purl.org/kid/ns#" py:choose="">
          <span py:when="1 == 1">1</span>
          <span py:when="2 == 2">2</span>
          <span py:when="3 == 3">3</span>
        </div>""")
        self.assertEqual("""<div>
          <span>1</span>
        </div>""", str(tmpl.generate()))

    def test_otherwise(self):
        tmpl = Template("""<div xmlns:py="http://purl.org/kid/ns#" py:choose="">
          <span py:when="False">hidden</span>
          <span py:otherwise="">hello</span>
        </div>""")
        self.assertEqual("""<div>
          <span>hello</span>
        </div>""", str(tmpl.generate()))

    def test_nesting(self):
        """
        Verify that `py:choose` blocks can be nested:
        """
        tmpl = Template("""<doc xmlns:py="http://purl.org/kid/ns#">
          <div py:choose="1">
            <div py:when="1" py:choose="3">
              <span py:when="2">2</span>
              <span py:when="3">3</span>
            </div>
          </div>
        </doc>""")
        self.assertEqual("""<doc>
          <div>
            <div>
              <span>3</span>
            </div>
          </div>
        </doc>""", str(tmpl.generate()))

    def test_when_with_strip(self):
        """
        Verify that a when directive with a strip directive actually strips of
        the outer element.
        """
        tmpl = Template("""<doc xmlns:py="http://purl.org/kid/ns#">
          <div py:choose="" py:strip="">
            <span py:otherwise="">foo</span>
          </div>
        </doc>""")
        self.assertEqual("""<doc>
            <span>foo</span>
        </doc>""", str(tmpl.generate()))


class DefDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:def` template directive."""

    def test_function_with_strip(self):
        """
        Verify that a named template function with a strip directive actually
        strips of the outer element.
        """
        tmpl = Template("""<doc xmlns:py="http://purl.org/kid/ns#">
          <div py:def="echo(what)" py:strip="">
            <b>${what}</b>
          </div>
          ${echo('foo')}
        </doc>""")
        self.assertEqual("""<doc>
            <b>foo</b>
        </doc>""", str(tmpl.generate()))


class ForDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:for` template directive."""

    def test_loop_with_strip(self):
        """
        Verify that the combining the `py:for` directive with `py:strip` works
        correctly.
        """
        tmpl = Template("""<doc xmlns:py="http://purl.org/kid/ns#">
          <div py:for="item in items" py:strip="">
            <b>${item}</b>
          </div>
        </doc>""")
        self.assertEqual("""<doc>
            <b>1</b>
            <b>2</b>
            <b>3</b>
            <b>4</b>
            <b>5</b>
        </doc>""", str(tmpl.generate(Context(items=range(1, 6)))))


class MatchDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:match` template directive."""

    def test_with_strip(self):
        """
        Verify that a match template can produce the same kind of element that
        it matched without entering an infinite recursion.
        """
        tmpl = Template("""<doc xmlns:py="http://purl.org/kid/ns#">
          <elem py:match="elem" py:strip="">
            <div class="elem">${select('*/text()')}</div>
          </elem>
          <elem>Hey Joe</elem>
        </doc>""")
        self.assertEqual("""<doc>
            <div class="elem">Hey Joe</div>
        </doc>""", str(tmpl.generate()))

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

    def test_interpolate_non_string_attrs(self):
        ctxt = Context()
        tmpl = Template('<root attr="${1}"/>')
        self.assertEqual('<root attr="1"/>', str(tmpl.generate(ctxt)))

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
    suite.addTest(unittest.makeSuite(AttrsDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ChooseDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(DefDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ForDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(MatchDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(StripDirectiveTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
