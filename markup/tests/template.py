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
import os
import unittest
import shutil
import sys
import tempfile

from markup.core import Markup, Stream
from markup.template import BadDirectiveError, Template, TemplateLoader, \
                            TemplateSyntaxError


class AttrsDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:attrs` template directive."""

    def test_combined_with_loop(self):
        """
        Verify that the directive has access to the loop variables.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <elem py:for="item in items" py:attrs="item"/>
        </doc>""")
        items = [{'id': 1, 'class': 'foo'}, {'id': 2, 'class': 'bar'}]
        self.assertEqual("""<doc>
          <elem id="1" class="foo"/><elem id="2" class="bar"/>
        </doc>""", str(tmpl.generate(items=items)))

    def test_update_existing_attr(self):
        """
        Verify that an attribute value that evaluates to `None` removes an
        existing attribute of that name.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <elem class="foo" py:attrs="{'class': 'bar'}"/>
        </doc>""")
        self.assertEqual("""<doc>
          <elem class="bar"/>
        </doc>""", str(tmpl.generate()))

    def test_remove_existing_attr(self):
        """
        Verify that an attribute value that evaluates to `None` removes an
        existing attribute of that name.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <elem class="foo" py:attrs="{'class': None}"/>
        </doc>""")
        self.assertEqual("""<doc>
          <elem/>
        </doc>""", str(tmpl.generate()))


class ChooseDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:choose` template directive and the complementary
    directives `py:when` and `py:otherwise`."""

    def test_multiple_true_whens(self):
        """
        Verify that, if multiple `py:when` bodies match, only the first is
        output.
        """
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/" py:choose="">
          <span py:when="1 == 1">1</span>
          <span py:when="2 == 2">2</span>
          <span py:when="3 == 3">3</span>
        </div>""")
        self.assertEqual("""<div>
          <span>1</span>
        </div>""", str(tmpl.generate()))

    def test_otherwise(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/" py:choose="">
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
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
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
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <div py:choose="" py:strip="">
            <span py:otherwise="">foo</span>
          </div>
        </doc>""")
        self.assertEqual("""<doc>
            <span>foo</span>
        </doc>""", str(tmpl.generate()))

    def test_as_element(self):
        """
        Verify that the directive can also be used as an element.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <py:choose>
            <py:when test="1 == 1">1</py:when>
            <py:when test="2 == 2">2</py:when>
            <py:when test="3 == 3">3</py:when>
          </py:choose>
        </doc>""")
        self.assertEqual("""<doc>
            1
        </doc>""", str(tmpl.generate()))


class DefDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:def` template directive."""

    def test_function_with_strip(self):
        """
        Verify that a named template function with a strip directive actually
        strips of the outer element.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <div py:def="echo(what)" py:strip="">
            <b>${what}</b>
          </div>
          ${echo('foo')}
        </doc>""")
        self.assertEqual("""<doc>
            <b>foo</b>
        </doc>""", str(tmpl.generate()))

    def test_exec_in_replace(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          <p py:def="echo(greeting, name='world')" class="message">
            ${greeting}, ${name}!
          </p>
          <div py:replace="echo('hello')"></div>
        </div>""")
        self.assertEqual("""<div>
          <p class="message">
            hello, world!
          </p>
        </div>""", str(tmpl.generate()))

    def test_as_element(self):
        """
        Verify that the directive can also be used as an element.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <py:def function="echo(what)">
            <b>${what}</b>
          </py:def>
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
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
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
        </doc>""", str(tmpl.generate(items=range(1, 6))))

    def test_as_element(self):
        """
        Verify that the directive can also be used as an element.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <py:for each="item in items">
            <b>${item}</b>
          </py:for>
        </doc>""")
        self.assertEqual("""<doc>
            <b>1</b>
            <b>2</b>
            <b>3</b>
            <b>4</b>
            <b>5</b>
        </doc>""", str(tmpl.generate(items=range(1, 6))))


class IfDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:if` template directive."""

    def test_loop_with_strip(self):
        """
        Verify that the combining the `py:if` directive with `py:strip` works
        correctly.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <b py:if="foo" py:strip="">${bar}</b>
        </doc>""")
        self.assertEqual("""<doc>
          Hello
        </doc>""", str(tmpl.generate(foo=True, bar='Hello')))

    def test_as_element(self):
        """
        Verify that the directive can also be used as an element.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <py:if test="foo">${bar}</py:if>
        </doc>""")
        self.assertEqual("""<doc>
          Hello
        </doc>""", str(tmpl.generate(foo=True, bar='Hello')))


class MatchDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:match` template directive."""

    def test_with_strip(self):
        """
        Verify that a match template can produce the same kind of element that
        it matched without entering an infinite recursion.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
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
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
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

    def test_as_element(self):
        """
        Verify that the directive can also be used as an element.
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <py:match path="elem">
            <div class="elem">${select('*/text()')}</div>
          </py:match>
          <elem>Hey Joe</elem>
        </doc>""")
        self.assertEqual("""<doc>
            <div class="elem">Hey Joe</div>
        </doc>""", str(tmpl.generate()))

    def test_recursive_match_1(self):
        """
        Match directives are applied recursively, meaning that they are also
        applied to any content they may have produced themselves:
        """
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
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
        tmpl = Template("""<html xmlns:py="http://markup.edgewall.org/">
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

    def test_select_all_attrs(self):
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <div py:match="elem" py:attrs="select('@*')">
            ${select('*/text()')}
          </div>
          <elem id="joe">Hey Joe</elem>
        </doc>""")
        self.assertEqual("""<doc>
          <div id="joe">
            Hey Joe
          </div>
        </doc>""", str(tmpl.generate()))

    def test_select_all_attrs_empty(self):
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <div py:match="elem" py:attrs="select('@*')">
            ${select('*/text()')}
          </div>
          <elem>Hey Joe</elem>
        </doc>""")
        self.assertEqual("""<doc>
          <div>
            Hey Joe
          </div>
        </doc>""", str(tmpl.generate()))

    def test_select_all_attrs_in_body(self):
        tmpl = Template("""<doc xmlns:py="http://markup.edgewall.org/">
          <div py:match="elem">
            Hey ${select('text()')} ${select('@*')}
          </div>
          <elem title="Cool">Joe</elem>
        </doc>""")
        self.assertEqual("""<doc>
          <div>
            Hey Joe Cool
          </div>
        </doc>""", str(tmpl.generate()))


class StripDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:strip` template directive."""

    def test_strip_false(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          <div py:strip="False"><b>foo</b></div>
        </div>""")
        self.assertEqual("""<div>
          <div><b>foo</b></div>
        </div>""", str(tmpl.generate()))

    def test_strip_empty(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          <div py:strip=""><b>foo</b></div>
        </div>""")
        self.assertEqual("""<div>
          <b>foo</b>
        </div>""", str(tmpl.generate()))


class WithDirectiveTestCase(unittest.TestCase):
    """Tests for the `py:with` template directive."""

    def test_shadowing(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          ${x}
          <span py:with="x = x * 2" py:replace="x"/>
          ${x}
        </div>""")
        self.assertEqual("""<div>
          42
          84
          42
        </div>""", str(tmpl.generate(x=42)))

    def test_as_element(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          <py:with vars="x = x * 2">${x}</py:with>
        </div>""")
        self.assertEqual("""<div>
          84
        </div>""", str(tmpl.generate(x=42)))


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

    def test_interpolate_mixed3(self):
        tmpl = Template('<root> ${var} $var</root>')
        self.assertEqual('<root> 42 42</root>', str(tmpl.generate(var=42)))

    def test_interpolate_non_string_attrs(self):
        tmpl = Template('<root attr="${1}"/>')
        self.assertEqual('<root attr="1"/>', str(tmpl.generate()))

    def test_interpolate_list_result(self):
        tmpl = Template('<root>$foo</root>')
        self.assertEqual('<root>buzz</root>', str(tmpl.generate(foo=('buzz',))))

    def test_empty_attr(self):
        tmpl = Template('<root attr=""/>')
        self.assertEqual('<root attr=""/>', str(tmpl.generate()))

    def test_bad_directive_error(self):
        xml = '<p xmlns:py="http://markup.edgewall.org/" py:do="nothing" />'
        try:
            tmpl = Template(xml, filename='test.html')
        except BadDirectiveError, e:
            self.assertEqual('test.html', e.filename)
            if sys.version_info[:2] >= (2, 4):
                self.assertEqual(1, e.lineno)

    def test_directive_value_syntax_error(self):
        xml = """<p xmlns:py="http://markup.edgewall.org/" py:if="bar'" />"""
        try:
            tmpl = Template(xml, filename='test.html')
            self.fail('Expected SyntaxError')
        except TemplateSyntaxError, e:
            self.assertEqual('test.html', e.filename)
            if sys.version_info[:2] >= (2, 4):
                self.assertEqual(1, e.lineno)

    def test_expression_syntax_error(self):
        xml = """<p>
          Foo <em>${bar"}</em>
        </p>"""
        try:
            tmpl = Template(xml, filename='test.html')
            self.fail('Expected SyntaxError')
        except TemplateSyntaxError, e:
            self.assertEqual('test.html', e.filename)
            if sys.version_info[:2] >= (2, 4):
                self.assertEqual(2, e.lineno)

    def test_expression_syntax_error_multi_line(self):
        xml = """<p><em></em>

 ${bar"}

        </p>"""
        try:
            tmpl = Template(xml, filename='test.html')
            self.fail('Expected SyntaxError')
        except TemplateSyntaxError, e:
            self.assertEqual('test.html', e.filename)
            if sys.version_info[:2] >= (2, 4):
                self.assertEqual(3, e.lineno)

    def test_markup_noescape(self):
        """
        Verify that outputting context data that is a `Markup` instance is not
        escaped.
        """
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          $myvar
        </div>""")
        self.assertEqual("""<div>
          <b>foo</b>
        </div>""", str(tmpl.generate(myvar=Markup('<b>foo</b>'))))

    def test_text_noescape_quotes(self):
        """
        Verify that outputting context data in text nodes doesn't escape quotes.
        """
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          $myvar
        </div>""")
        self.assertEqual("""<div>
          "foo"
        </div>""", str(tmpl.generate(myvar='"foo"')))

    def test_attr_escape_quotes(self):
        """
        Verify that outputting context data in attribtes escapes quotes.
        """
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          <elem class="$myvar"/>
        </div>""")
        self.assertEqual("""<div>
          <elem class="&#34;foo&#34;"/>
        </div>""", str(tmpl.generate(myvar='"foo"')))

    def test_directive_element(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          <py:if test="myvar">bar</py:if>
        </div>""")
        self.assertEqual("""<div>
          bar
        </div>""", str(tmpl.generate(myvar='"foo"')))

    def test_normal_comment(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          <!-- foo bar -->
        </div>""")
        self.assertEqual("""<div>
          <!-- foo bar -->
        </div>""", str(tmpl.generate()))

    def test_template_comment(self):
        tmpl = Template("""<div xmlns:py="http://markup.edgewall.org/">
          <!-- !foo -->
          <!--!bar-->
        </div>""")
        self.assertEqual("""<div>
        </div>""", str(tmpl.generate()))


class TemplateLoaderTestCase(unittest.TestCase):
    """Tests for the template loader."""

    def setUp(self):
        self.dirname = tempfile.mkdtemp(suffix='markup_test')

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_relative_include_samedir(self):
        file1 = open(os.path.join(self.dirname, 'tmpl1.html'), 'w')
        try:
            file1.write("""<div>Included</div>""")
        finally:
            file1.close()

        file2 = open(os.path.join(self.dirname, 'tmpl2.html'), 'w')
        try:
            file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude">
  <xi:include href="tmpl1.html" />
</html>""")
        finally:
            file2.close()

        loader = TemplateLoader([self.dirname])
        tmpl = loader.load('tmpl2.html')
        self.assertEqual("""<html>
  <div>Included</div>
</html>""", tmpl.generate().render())

    def test_relative_include_subdir(self):
        os.mkdir(os.path.join(self.dirname, 'sub'))
        file1 = open(os.path.join(self.dirname, 'sub', 'tmpl1.html'), 'w')
        try:
            file1.write("""<div>Included</div>""")
        finally:
            file1.close()

        file2 = open(os.path.join(self.dirname, 'tmpl2.html'), 'w')
        try:
            file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude">
  <xi:include href="sub/tmpl1.html" />
</html>""")
        finally:
            file2.close()

        loader = TemplateLoader([self.dirname])
        tmpl = loader.load('tmpl2.html')
        self.assertEqual("""<html>
  <div>Included</div>
</html>""", tmpl.generate().render())

    def test_relative_include_parentdir(self):
        file1 = open(os.path.join(self.dirname, 'tmpl1.html'), 'w')
        try:
            file1.write("""<div>Included</div>""")
        finally:
            file1.close()

        os.mkdir(os.path.join(self.dirname, 'sub'))
        file2 = open(os.path.join(self.dirname, 'sub', 'tmpl2.html'), 'w')
        try:
            file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude">
  <xi:include href="../tmpl1.html" />
</html>""")
        finally:
            file2.close()

        loader = TemplateLoader([self.dirname])
        tmpl = loader.load('sub/tmpl2.html')
        self.assertEqual("""<html>
  <div>Included</div>
</html>""", tmpl.generate().render())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(Template.__module__))
    suite.addTest(unittest.makeSuite(AttrsDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ChooseDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(DefDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ForDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(IfDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(MatchDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(StripDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(WithDirectiveTestCase, 'test'))
    suite.addTest(unittest.makeSuite(TemplateTestCase, 'test'))
    suite.addTest(unittest.makeSuite(TemplateLoaderTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
