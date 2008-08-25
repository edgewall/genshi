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
import unittest

from genshi.input import XML
from genshi.path import Path, PathParser, PathSyntaxError, GenericStrategy, \
                        SingleStepStrategy, SimplePathStrategy


class FakePath(Path):
    def __init__(self, strategy):
        self.strategy = strategy
    def test(self, ignore_context = False):
        return self.strategy.test(ignore_context)

class PathTestCase(unittest.TestCase):

    strategies = [GenericStrategy, SingleStepStrategy, SimplePathStrategy]
    def _create_path(self, expression, expected):
        return path

    def _test_strategies(self, stream, path, render,
                             namespaces=None, variables=None):
        for strategy in self.strategies:
            if not strategy.supports(path):
                continue
            s = strategy(path)
            rendered = FakePath(s).select(stream,namespaces=namespaces,
                                            variables=variables).render()
            msg = "Bad render using %s strategy"%str(strategy)
            msg += "\nExpected:\t'%s'"%render
            msg += "\nRendered:\t'%s'"%rendered
            self.assertEqual(render, rendered, msg)

    def _test_expression(self, text, expected, stream=None, render="",
                            namespaces=None, variables=None):
        path = Path(text)
        if expected is not None:
            self.assertEqual(expected, repr(path))

        if stream is None:
            return

        rendered = path.select(stream, namespaces=namespaces,
                                    variables=variables).render()
        msg = "Bad render using whole path"
        msg += "\nExpected:\t'%s'"%render
        msg += "\nRendered:\t'%s'"%rendered
        self.assertEqual(render, rendered, msg)

        if len(path.paths) == 1:
            self._test_strategies(stream, path.paths[0], render,
                                namespaces=namespaces, variables=variables)


    def test_error_no_absolute_path(self):
        self.assertRaises(PathSyntaxError, Path, '/root')

    def test_error_unsupported_axis(self):
        self.assertRaises(PathSyntaxError, Path, '..')
        self.assertRaises(PathSyntaxError, Path, 'parent::ma')

    def test_1step(self):
        xml = XML('<root><elem/></root>')

        self._test_expression(  'elem',
                                '<Path "child::elem">',
                                xml,
                                '<elem/>')

        self._test_expression(  'elem',
                                '<Path "child::elem">',
                                xml,
                                '<elem/>')

        self._test_expression(  'child::elem',
                                '<Path "child::elem">',
                                xml,
                                '<elem/>')

        self._test_expression(  '//elem',
                                '<Path "descendant-or-self::elem">',
                                xml,
                                '<elem/>')

        self._test_expression(  'descendant::elem',
                                '<Path "descendant::elem">',
                                xml,
                                '<elem/>')

    def test_1step_self(self):
        xml = XML('<root><elem/></root>')

        self._test_expression(  '.',
                                '<Path "self::node()">',
                                xml,
                                '<root><elem/></root>')

        self._test_expression(  'self::node()',
                                '<Path "self::node()">',
                                xml,
                                '<root><elem/></root>')

    def test_1step_wildcard(self):
        xml = XML('<root><elem/></root>')

        self._test_expression(  '*',
                                '<Path "child::*">',
                                xml,
                                '<elem/>')

        self._test_expression(  'child::*',
                                '<Path "child::*">',
                                xml,
                                '<elem/>')

        self._test_expression(  'child::node()',
                                '<Path "child::node()">',
                                xml,
                                '<elem/>')

        self._test_expression(  '//*',
                                '<Path "descendant-or-self::*">',
                                xml,
                                '<root><elem/></root>')

    def test_1step_attribute(self):
        self._test_expression(  '@foo',
                                '<Path "attribute::foo">',
                                XML('<root/>'),
                                '')

        xml = XML('<root foo="bar"/>')

        self._test_expression(  '@foo',
                                '<Path "attribute::foo">',
                                xml,
                                'bar')

        self._test_expression(  './@foo',
                                '<Path "self::node()/attribute::foo">',
                                xml,
                                'bar')

    def test_1step_text(self):
        xml = XML('<root>Hey</root>')

        self._test_expression(  'text()',
                                '<Path "child::text()">',
                                xml,
                                'Hey')

        self._test_expression(  './text()',
                                '<Path "self::node()/child::text()">',
                                xml,
                                'Hey')

        self._test_expression(  '//text()',
                                '<Path "descendant-or-self::text()">',
                                xml,
                                'Hey')

        self._test_expression(  './/text()',
            '<Path "self::node()/descendant-or-self::node()/child::text()">',
                                xml,
                                'Hey')

    def test_2step(self):
        xml = XML('<root><foo/><bar/></root>')
        self._test_expression('*', None, xml, '<foo/><bar/>')
        self._test_expression('bar', None, xml, '<bar/>')
        self._test_expression('baz', None, xml, '')

    def test_2step_attribute(self):
        xml = XML('<elem class="x"><span id="joe">Hey Joe</span></elem>')
        self._test_expression('@*', None, xml, 'x')
        self._test_expression('./@*', None, xml, 'x')
        self._test_expression('.//@*', None, xml, 'xjoe')
        self._test_expression('*/@*', None, xml, 'joe')

        xml = XML('<elem><foo id="1"/><foo id="2"/></elem>')
        self._test_expression('@*', None, xml, '')
        self._test_expression('foo/@*', None, xml, '12')

    def test_2step_complex(self):
        xml = XML('<root><foo><bar/></foo></root>')

        self._test_expression(  'foo/bar',
                                '<Path "child::foo/child::bar">',
                                xml,
                                '<bar/>')

        self._test_expression(  './bar',
                                '<Path "self::node()/child::bar">',
                                xml,
                                '')

        self._test_expression(  'foo/*',
                                '<Path "child::foo/child::*">',
                                xml,
                                '<bar/>')

        xml = XML('<root><foo><bar id="1"/></foo><bar id="2"/></root>')
        self._test_expression(  './bar',
                                '<Path "self::node()/child::bar">',
                                xml,
                                '<bar id="2"/>')

    def test_2step_text(self):
        xml = XML('<root><item>Foo</item></root>')

        self._test_expression(  'item/text()',
                                '<Path "child::item/child::text()">',
                                xml,
                                'Foo')

        self._test_expression(  '*/text()',
                                '<Path "child::*/child::text()">',
                                xml,
                                'Foo')

        self._test_expression(  '//text()',
                                '<Path "descendant-or-self::text()">',
                                xml,
                                'Foo')

        self._test_expression(  './text()',
                                '<Path "self::node()/child::text()">',
                                xml,
                                '')

        xml = XML('<root><item>Foo</item><item>Bar</item></root>')
        self._test_expression(  'item/text()',
                                '<Path "child::item/child::text()">',
                                xml,
                                'FooBar')

    def test_3step(self):
        xml = XML('<root><foo><bar/></foo></root>')
        self._test_expression(  'foo/*',
                                '<Path "child::foo/child::*">',
                                xml,
                                '<bar/>')

    def test_3step_complex(self):
        xml = XML('<root><foo><bar/></foo></root>')
        self._test_expression(  '*/bar',
                                '<Path "child::*/child::bar">',
                                xml,
                                '<bar/>')

        xml = XML('<root><foo><bar id="1"/></foo><bar id="2"/></root>')
        self._test_expression(  '//bar',
                                '<Path "descendant-or-self::bar">',
                                xml,
                                '<bar id="1"/><bar id="2"/>')

    def test_node_type_comment(self):
        xml = XML('<root><!-- commented --></root>')
        self._test_expression(  'comment()',
                                '<Path "child::comment()">',
                                xml,
                                '<!-- commented -->')

    def test_node_type_text(self):
        xml = XML('<root>Some text <br/>in here.</root>')
        self._test_expression(  'text()',
                                '<Path "child::text()">',
                                xml,
                                'Some text in here.')

    def test_node_type_node(self):
        xml = XML('<root>Some text <br/>in here.</root>')
        self._test_expression(  'node()',
                                '<Path "child::node()">',
                                xml,
                                'Some text <br/>in here.',)

    def test_node_type_processing_instruction(self):
        xml = XML('<?python x = 2 * 3 ?><root><?php echo("x") ?></root>')

        self._test_expression(  '//processing-instruction()',
                        '<Path "descendant-or-self::processing-instruction()">',
                                xml,
                                '<?python x = 2 * 3 ?><?php echo("x") ?>')

        self._test_expression(  'processing-instruction()',
                                '<Path "child::processing-instruction()">',
                                xml,
                                '<?php echo("x") ?>')

        self._test_expression(  'processing-instruction("php")',
                        '<Path "child::processing-instruction(\"php\")">',
                                xml,
                                '<?php echo("x") ?>')

    def test_simple_union(self):
        xml = XML("""<body>1<br />2<br />3<br /></body>""")
        self._test_expression(  '*|text()',
                                '<Path "child::*|child::text()">',
                                xml,
                                '1<br/>2<br/>3<br/>')

    def test_predicate_name(self):
        xml = XML('<root><foo/><bar/></root>')
        self._test_expression('*[name()="foo"]', None, xml, '<foo/>')

    def test_predicate_localname(self):
        xml = XML('<root><foo xmlns="NS"/><bar/></root>')
        self._test_expression('*[local-name()="foo"]', None, xml,
                                '<foo xmlns="NS"/>')

    def test_predicate_namespace(self):
        xml = XML('<root><foo xmlns="NS"/><bar/></root>')
        self._test_expression('*[namespace-uri()="NS"]', None, xml,
                                '<foo xmlns="NS"/>')

    def test_predicate_not_name(self):
        xml = XML('<root><foo/><bar/></root>')
        self._test_expression('*[not(name()="foo")]', None, xml, '<bar/>')

    def test_predicate_attr(self):
        xml = XML('<root><item/><item important="very"/></root>')
        self._test_expression('item[@important]', None, xml,
                                '<item important="very"/>')
        self._test_expression('item[@important="very"]', None, xml,
                                '<item important="very"/>')

    def test_predicate_attr_equality(self):
        xml = XML('<root><item/><item important="notso"/></root>')
        self._test_expression('item[@important="very"]', None, xml, '')
        self._test_expression('item[@important!="very"]', None, xml,
                                '<item/><item important="notso"/>')

    def test_predicate_attr_greater_than(self):
        xml = XML('<root><item priority="3"/></root>')
        self._test_expression('item[@priority>3]', None, xml, '')
        self._test_expression('item[@priority>2]', None, xml,
                                '<item priority="3"/>')

    def test_predicate_attr_less_than(self):
        xml = XML('<root><item priority="3"/></root>')
        self._test_expression('item[@priority<3]', None, xml, '')
        self._test_expression('item[@priority<4]', None, xml,
                                '<item priority="3"/>')

    def test_predicate_attr_and(self):
        xml = XML('<root><item/><item important="very"/></root>')
        self._test_expression('item[@important and @important="very"]',
                                None, xml, '<item important="very"/>')
        self._test_expression('item[@important and @important="notso"]',
                                None, xml, '')

    def test_predicate_attr_or(self):
        xml = XML('<root><item/><item important="very"/></root>')
        self._test_expression('item[@urgent or @important]', None, xml,
                                '<item important="very"/>')
        self._test_expression('item[@urgent or @notso]', None, xml, '')

    def test_predicate_boolean_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[boolean("")]', None, xml, '')
        self._test_expression('*[boolean("yo")]', None, xml, '<foo>bar</foo>')
        self._test_expression('*[boolean(0)]', None, xml, '')
        self._test_expression('*[boolean(42)]', None, xml, '<foo>bar</foo>')
        self._test_expression('*[boolean(false())]', None, xml, '')
        self._test_expression('*[boolean(true())]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_ceil_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[ceiling("4.5")=5]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_concat_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[name()=concat("f", "oo")]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_contains_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[contains(name(), "oo")]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_matches_function(self):
        xml = XML('<root><foo>bar</foo><bar>foo</bar></root>')
        self._test_expression('*[matches(name(), "foo|bar")]', None, xml,
                                '<foo>bar</foo><bar>foo</bar>')

    def test_predicate_false_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[false()]', None, xml, '')

    def test_predicate_floor_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[floor("4.5")=4]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_normalize_space_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[normalize-space(" foo   bar  ")="foo bar"]',
                                None, xml, '<foo>bar</foo>')

    def test_predicate_number_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[number("3.0")=3]', None, xml,
                                 '<foo>bar</foo>')
        self._test_expression('*[number("3.0")=3.0]', None, xml,
                                '<foo>bar</foo>')
        self._test_expression('*[number("0.1")=.1]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_round_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[round("4.4")=4]', None, xml,
                                '<foo>bar</foo>')
        self._test_expression('*[round("4.6")=5]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_starts_with_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[starts-with(name(), "f")]', None, xml,
                                '<foo>bar</foo>')
        self._test_expression('*[starts-with(name(), "b")]', None, xml, '')

    def test_predicate_string_length_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[string-length(name())=3]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_substring_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[substring(name(), 1)="oo"]', None, xml,
                                '<foo>bar</foo>')
        self._test_expression('*[substring(name(), 1, 1)="o"]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_substring_after_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[substring-after(name(), "f")="oo"]', None, xml,
                                '<foo>bar</foo>')

    def test_predicate_substring_before_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[substring-before(name(), "oo")="f"]',
                                None, xml, '<foo>bar</foo>')

    def test_predicate_translate_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[translate(name(), "fo", "ba")="baa"]',
                                None, xml, '<foo>bar</foo>')

    def test_predicate_true_function(self):
        xml = XML('<root><foo>bar</foo></root>')
        self._test_expression('*[true()]', None, xml, '<foo>bar</foo>')

    def test_predicate_variable(self):
        xml = XML('<root><foo>bar</foo></root>')
        variables = {'bar': 'foo'}
        self._test_expression('*[name()=$bar]', None, xml, '<foo>bar</foo>',
                                variables = variables)

    def test_predicate_position(self):
        xml = XML('<root><foo id="a1"/><foo id="a2"/><foo id="a3"/></root>')
        self._test_expression('*[2]', None, xml, '<foo id="a2"/>')

    def test_predicate_attr_and_position(self):
        xml = XML('<root><foo/><foo id="a1"/><foo id="a2"/></root>')
        self._test_expression('*[@id][2]', None, xml, '<foo id="a2"/>')

    def test_predicate_position_and_attr(self):
        xml = XML('<root><foo/><foo id="a1"/><foo id="a2"/></root>')
        self._test_expression('*[1][@id]', None, xml, '')
        self._test_expression('*[2][@id]', None, xml, '<foo id="a1"/>')

    def test_predicate_advanced_position(self):
        xml = XML('<root><a><b><c><d><e/></d></c></b></a></root>')
        self._test_expression(   'descendant-or-self::*/'
                                'descendant-or-self::*/'
                                'descendant-or-self::*[2]/'
                                'self::*/descendant::*[3]', None, xml,
                                '<d><e/></d>')

    def test_predicate_child_position(self):
        xml = XML('\
<root><a><b>1</b><b>2</b><b>3</b></a><a><b>4</b><b>5</b></a></root>')
        self._test_expression('//a/b[2]', None, xml, '<b>2</b><b>5</b>')
        self._test_expression('//a/b[3]', None, xml, '<b>3</b>')

    def test_name_with_namespace(self):
        xml = XML('<root xmlns:f="FOO"><f:foo>bar</f:foo></root>')
        self._test_expression('f:foo', '<Path "child::f:foo">', xml,
                                '<foo xmlns="FOO">bar</foo>',
                                namespaces = {'f': 'FOO'})

    def test_wildcard_with_namespace(self):
        xml = XML('<root xmlns:f="FOO"><f:foo>bar</f:foo></root>')
        self._test_expression('f:*', '<Path "child::f:*">', xml,
                                '<foo xmlns="FOO">bar</foo>',
                                namespaces = {'f': 'FOO'})

    def test_predicate_termination(self):
        """
        Verify that a patch matching the self axis with a predicate doesn't
        cause an infinite loop. See <http://genshi.edgewall.org/ticket/82>.
        """
        xml = XML('<ul flag="1"><li>a</li><li>b</li></ul>')
        self._test_expression('.[@flag="1"]/*', None, xml,
                                '<li>a</li><li>b</li>')

        xml = XML('<ul flag="1"><li>a</li><li>b</li></ul>')
        self._test_expression('.[@flag="0"]/*', None, xml, '')

    def test_attrname_with_namespace(self):
        xml = XML('<root xmlns:f="FOO"><foo f:bar="baz"/></root>')
        self._test_expression('foo[@f:bar]', None, xml,
                                '<foo xmlns:ns1="FOO" ns1:bar="baz"/>',
                                namespaces={'f': 'FOO'})

    def test_attrwildcard_with_namespace(self):
        xml = XML('<root xmlns:f="FOO"><foo f:bar="baz"/></root>')
        self._test_expression('foo[@f:*]', None, xml,
                                '<foo xmlns:ns1="FOO" ns1:bar="baz"/>',
                                namespaces={'f': 'FOO'})
    def test_self_and_descendant(self):
        xml = XML('<root><foo/></root>')
        self._test_expression('self::root', None, xml, '<root><foo/></root>')
        self._test_expression('self::foo', None, xml, '')
        self._test_expression('descendant::root', None, xml, '')
        self._test_expression('descendant::foo', None, xml, '<foo/>')
        self._test_expression('descendant-or-self::root', None, xml, 
                                '<root><foo/></root>')
        self._test_expression('descendant-or-self::foo', None, xml, '<foo/>')

    def test_long_simple_paths(self):
        xml = XML('<root><a><b><a><d><a><b><a><b><a><b><a><c>!'
                    '</c></a></b></a></b></a></b></a></d></a></b></a></root>')
        self._test_expression('//a/b/a/b/a/c', None, xml, '<c>!</c>')
        self._test_expression('//a/b/a/c', None, xml, '<c>!</c>')
        self._test_expression('//a/c', None, xml, '<c>!</c>')
        self._test_expression('//c', None, xml, '<c>!</c>')
        # Please note that a//b is NOT the same as a/descendant::b 
        # it is a/descendant-or-self::node()/b, which SimplePathStrategy
        # does NOT support
        self._test_expression('a/b/descendant::a/c', None, xml, '<c>!</c>')
        self._test_expression('a/b/descendant::a/d/descendant::a/c',
                                None, xml, '<c>!</c>')
        self._test_expression('a/b/descendant::a/d/a/c', None, xml, '')
        self._test_expression('//d/descendant::b/descendant::b/descendant::b'
                                '/descendant::c', None, xml, '<c>!</c>')
        self._test_expression('//d/descendant::b/descendant::b/descendant::b'
                                '/descendant::b/descendant::c', None, xml, '')
    def _test_support(self, strategy_class, text):
        path = PathParser(text, None, -1).parse()[0]
        return strategy_class.supports(path)
    def test_simple_strategy_support(self):
        self.assert_(self._test_support(SimplePathStrategy, 'a/b'))
        self.assert_(self._test_support(SimplePathStrategy, 'self::a/b'))
        self.assert_(self._test_support(SimplePathStrategy, 'descendant::a/b'))
        self.assert_(self._test_support(SimplePathStrategy,
                         'descendant-or-self::a/b'))
        self.assert_(self._test_support(SimplePathStrategy, '//a/b'))
        self.assert_(self._test_support(SimplePathStrategy, 'a/@b'))
        self.assert_(self._test_support(SimplePathStrategy, 'a/text()'))

        # a//b is a/descendant-or-self::node()/b
        self.assert_(not self._test_support(SimplePathStrategy, 'a//b'))
        self.assert_(not self._test_support(SimplePathStrategy, 'node()/@a'))
        self.assert_(not self._test_support(SimplePathStrategy, '@a'))
        self.assert_(not self._test_support(SimplePathStrategy, 'foo:bar'))
        self.assert_(not self._test_support(SimplePathStrategy, 'a/@foo:bar'))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(Path.__module__))
    suite.addTest(unittest.makeSuite(PathTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
