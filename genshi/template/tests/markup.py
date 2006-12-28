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
from StringIO import StringIO
import sys
import tempfile
import unittest

from genshi.core import Markup
from genshi.input import XML
from genshi.template.core import BadDirectiveError, TemplateSyntaxError
from genshi.template.loader import TemplateLoader
from genshi.template.markup import MarkupTemplate


class MarkupTemplateTestCase(unittest.TestCase):
    """Tests for markup template processing."""

    def test_parse_fileobj(self):
        fileobj = StringIO('<root> ${var} $var</root>')
        tmpl = MarkupTemplate(fileobj)
        self.assertEqual('<root> 42 42</root>', str(tmpl.generate(var=42)))

    def test_parse_stream(self):
        stream = XML('<root> ${var} $var</root>')
        tmpl = MarkupTemplate(stream)
        self.assertEqual('<root> 42 42</root>', str(tmpl.generate(var=42)))

    def test_interpolate_mixed3(self):
        tmpl = MarkupTemplate('<root> ${var} $var</root>')
        self.assertEqual('<root> 42 42</root>', str(tmpl.generate(var=42)))

    def test_interpolate_leading_trailing_space(self):
        tmpl = MarkupTemplate('<root>${    foo    }</root>')
        self.assertEqual('<root>bar</root>', str(tmpl.generate(foo='bar')))

    def test_interpolate_multiline(self):
        tmpl = MarkupTemplate("""<root>${dict(
          bar = 'baz'
        )[foo]}</root>""")
        self.assertEqual('<root>baz</root>', str(tmpl.generate(foo='bar')))

    def test_interpolate_non_string_attrs(self):
        tmpl = MarkupTemplate('<root attr="${1}"/>')
        self.assertEqual('<root attr="1"/>', str(tmpl.generate()))

    def test_interpolate_list_result(self):
        tmpl = MarkupTemplate('<root>$foo</root>')
        self.assertEqual('<root>buzz</root>', str(tmpl.generate(foo=('buzz',))))

    def test_empty_attr(self):
        tmpl = MarkupTemplate('<root attr=""/>')
        self.assertEqual('<root attr=""/>', str(tmpl.generate()))

    def test_bad_directive_error(self):
        xml = '<p xmlns:py="http://genshi.edgewall.org/" py:do="nothing" />'
        try:
            tmpl = MarkupTemplate(xml, filename='test.html')
        except BadDirectiveError, e:
            self.assertEqual('test.html', e.filename)
            if sys.version_info[:2] >= (2, 4):
                self.assertEqual(1, e.lineno)

    def test_directive_value_syntax_error(self):
        xml = """<p xmlns:py="http://genshi.edgewall.org/" py:if="bar'" />"""
        try:
            tmpl = MarkupTemplate(xml, filename='test.html')
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
            tmpl = MarkupTemplate(xml, filename='test.html')
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
            tmpl = MarkupTemplate(xml, filename='test.html')
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
        tmpl = MarkupTemplate("""<div xmlns:py="http://genshi.edgewall.org/">
          $myvar
        </div>""")
        self.assertEqual("""<div>
          <b>foo</b>
        </div>""", str(tmpl.generate(myvar=Markup('<b>foo</b>'))))

    def test_text_noescape_quotes(self):
        """
        Verify that outputting context data in text nodes doesn't escape quotes.
        """
        tmpl = MarkupTemplate("""<div xmlns:py="http://genshi.edgewall.org/">
          $myvar
        </div>""")
        self.assertEqual("""<div>
          "foo"
        </div>""", str(tmpl.generate(myvar='"foo"')))

    def test_attr_escape_quotes(self):
        """
        Verify that outputting context data in attribtes escapes quotes.
        """
        tmpl = MarkupTemplate("""<div xmlns:py="http://genshi.edgewall.org/">
          <elem class="$myvar"/>
        </div>""")
        self.assertEqual("""<div>
          <elem class="&#34;foo&#34;"/>
        </div>""", str(tmpl.generate(myvar='"foo"')))

    def test_directive_element(self):
        tmpl = MarkupTemplate("""<div xmlns:py="http://genshi.edgewall.org/">
          <py:if test="myvar">bar</py:if>
        </div>""")
        self.assertEqual("""<div>
          bar
        </div>""", str(tmpl.generate(myvar='"foo"')))

    def test_normal_comment(self):
        tmpl = MarkupTemplate("""<div xmlns:py="http://genshi.edgewall.org/">
          <!-- foo bar -->
        </div>""")
        self.assertEqual("""<div>
          <!-- foo bar -->
        </div>""", str(tmpl.generate()))

    def test_template_comment(self):
        tmpl = MarkupTemplate("""<div xmlns:py="http://genshi.edgewall.org/">
          <!-- !foo -->
          <!--!bar-->
        </div>""")
        self.assertEqual("""<div>
        </div>""", str(tmpl.generate()))

    def test_parse_with_same_namespace_nested(self):
        tmpl = MarkupTemplate("""<div xmlns:py="http://genshi.edgewall.org/">
          <span xmlns:py="http://genshi.edgewall.org/">
          </span>
        </div>""")
        self.assertEqual("""<div>
          <span>
          </span>
        </div>""", str(tmpl.generate()))

    def test_latin1_encoded_with_xmldecl(self):
        tmpl = MarkupTemplate(u"""<?xml version="1.0" encoding="iso-8859-1" ?>
        <div xmlns:py="http://genshi.edgewall.org/">
          \xf6
        </div>""".encode('iso-8859-1'), encoding='iso-8859-1')
        self.assertEqual(u"""<div>
          \xf6
        </div>""", unicode(tmpl.generate()))

    def test_latin1_encoded_explicit_encoding(self):
        tmpl = MarkupTemplate(u"""<div xmlns:py="http://genshi.edgewall.org/">
          \xf6
        </div>""".encode('iso-8859-1'), encoding='iso-8859-1')
        self.assertEqual(u"""<div>
          \xf6
        </div>""", unicode(tmpl.generate()))

    def test_include_in_loop(self):
        dirname = tempfile.mkdtemp(suffix='genshi_test')
        try:
            file1 = open(os.path.join(dirname, 'tmpl1.html'), 'w')
            try:
                file1.write("""<div>Included $idx</div>""")
            finally:
                file1.close()

            file2 = open(os.path.join(dirname, 'tmpl2.html'), 'w')
            try:
                file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude"
                                     xmlns:py="http://genshi.edgewall.org/">
                  <xi:include href="${name}.html" py:for="idx in range(3)" />
                </html>""")
            finally:
                file2.close()

            loader = TemplateLoader([dirname])
            tmpl = loader.load('tmpl2.html')
            self.assertEqual("""<html>
                  <div>Included 0</div><div>Included 1</div><div>Included 2</div>
                </html>""", tmpl.generate(name='tmpl1').render())
        finally:
            shutil.rmtree(dirname)

    def test_dynamic_inlude_href(self):
        dirname = tempfile.mkdtemp(suffix='genshi_test')
        try:
            file1 = open(os.path.join(dirname, 'tmpl1.html'), 'w')
            try:
                file1.write("""<div>Included</div>""")
            finally:
                file1.close()

            file2 = open(os.path.join(dirname, 'tmpl2.html'), 'w')
            try:
                file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude"
                                     xmlns:py="http://genshi.edgewall.org/">
                  <xi:include href="${name}.html" />
                </html>""")
            finally:
                file2.close()

            loader = TemplateLoader([dirname])
            tmpl = loader.load('tmpl2.html')
            self.assertEqual("""<html>
                  <div>Included</div>
                </html>""", tmpl.generate(name='tmpl1').render())
        finally:
            shutil.rmtree(dirname)

    def test_select_inluded_elements(self):
        dirname = tempfile.mkdtemp(suffix='genshi_test')
        try:
            file1 = open(os.path.join(dirname, 'tmpl1.html'), 'w')
            try:
                file1.write("""<li>$item</li>""")
            finally:
                file1.close()

            file2 = open(os.path.join(dirname, 'tmpl2.html'), 'w')
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

            loader = TemplateLoader([dirname])
            tmpl = loader.load('tmpl2.html')
            self.assertEqual("""<html>
                  <ul><li>1</li><li>2</li><li>3</li></ul>
                </html>""", tmpl.generate().render())
        finally:
            shutil.rmtree(dirname)

    def test_fallback_when_include_found(self):
        dirname = tempfile.mkdtemp(suffix='genshi_test')
        try:
            file1 = open(os.path.join(dirname, 'tmpl1.html'), 'w')
            try:
                file1.write("""<div>Included</div>""")
            finally:
                file1.close()

            file2 = open(os.path.join(dirname, 'tmpl2.html'), 'w')
            try:
                file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude">
                  <xi:include href="tmpl1.html"><xi:fallback>
                    Missing</xi:fallback></xi:include>
                </html>""")
            finally:
                file2.close()

            loader = TemplateLoader([dirname])
            tmpl = loader.load('tmpl2.html')
            self.assertEqual("""<html>
                  <div>Included</div>
                </html>""", tmpl.generate().render())
        finally:
            shutil.rmtree(dirname)

    def test_fallback_when_include_not_found(self):
        dirname = tempfile.mkdtemp(suffix='genshi_test')
        try:
            file2 = open(os.path.join(dirname, 'tmpl2.html'), 'w')
            try:
                file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude">
                  <xi:include href="tmpl1.html"><xi:fallback>
                  Missing</xi:fallback></xi:include>
                </html>""")
            finally:
                file2.close()

            loader = TemplateLoader([dirname])
            tmpl = loader.load('tmpl2.html')
            self.assertEqual("""<html>
                  Missing
                </html>""", tmpl.generate().render())
        finally:
            shutil.rmtree(dirname)

    def test_include_in_fallback(self):
        dirname = tempfile.mkdtemp(suffix='genshi_test')
        try:
            file1 = open(os.path.join(dirname, 'tmpl1.html'), 'w')
            try:
                file1.write("""<div>Included</div>""")
            finally:
                file1.close()

            file2 = open(os.path.join(dirname, 'tmpl3.html'), 'w')
            try:
                file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude">
                  <xi:include href="tmpl2.html">
                    <xi:fallback>
                      <xi:include href="tmpl1.html">
                        <xi:fallback>Missing</xi:fallback>
                      </xi:include>
                    </xi:fallback>
                  </xi:include>
                </html>""")
            finally:
                file2.close()

            loader = TemplateLoader([dirname])
            tmpl = loader.load('tmpl3.html')
            self.assertEqual("""<html>
                  <div>Included</div>
                </html>""", tmpl.generate().render())
        finally:
            shutil.rmtree(dirname)

    def test_nested_include_fallback(self):
        dirname = tempfile.mkdtemp(suffix='genshi_test')
        try:
            file2 = open(os.path.join(dirname, 'tmpl3.html'), 'w')
            try:
                file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude">
                  <xi:include href="tmpl2.html">
                    <xi:fallback>
                      <xi:include href="tmpl1.html">
                        <xi:fallback>Missing</xi:fallback>
                      </xi:include>
                    </xi:fallback>
                  </xi:include>
                </html>""")
            finally:
                file2.close()

            loader = TemplateLoader([dirname])
            tmpl = loader.load('tmpl3.html')
            self.assertEqual("""<html>
                        Missing
                </html>""", tmpl.generate().render())
        finally:
            shutil.rmtree(dirname)

    def test_include_fallback_with_directive(self):
        dirname = tempfile.mkdtemp(suffix='genshi_test')
        try:
            file2 = open(os.path.join(dirname, 'tmpl2.html'), 'w')
            try:
                file2.write("""<html xmlns:xi="http://www.w3.org/2001/XInclude"
                      xmlns:py="http://genshi.edgewall.org/">
                  <xi:include href="tmpl1.html"><xi:fallback>
                    <py:if test="True">tmpl1.html not found</py:if>
                  </xi:fallback></xi:include>
                </html>""")
            finally:
                file2.close()

            loader = TemplateLoader([dirname])
            tmpl = loader.load('tmpl2.html')
            self.assertEqual("""<html>
                    tmpl1.html not found
                </html>""", tmpl.generate(debug=True).render())
        finally:
            shutil.rmtree(dirname)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(MarkupTemplate.__module__))
    suite.addTest(unittest.makeSuite(MarkupTemplateTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
