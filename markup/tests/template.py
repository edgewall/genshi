# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.

import doctest
import unittest
import sys

from markup.core import Stream
from markup.template import BadDirectiveError, Context, Template, \
                            TemplateSyntaxError


class TemplateTestCase(unittest.TestCase):

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
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
