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

from markup.input import XML
from markup.path import Path


class PathTestCase(unittest.TestCase):

    def test_1step(self):
        xml = XML('<root><elem/></root>')
        self.assertEqual('<elem/>', Path('elem').select(xml).render())
        self.assertEqual('<elem/>', Path('//elem').select(xml).render())
    
    def test_1step_wildcard(self):
        xml = XML('<root><elem/></root>')
        self.assertEqual('<elem/>', Path('*').select(xml).render())
        self.assertEqual('<elem/>', Path('//*').select(xml).render())
    
    def test_1step_attribute(self):
        path = Path('@foo')
        self.assertEqual('', path.select(XML('<root/>')).render())
        self.assertEqual('bar', path.select(XML('<root foo="bar"/>')).render())

    def test_1step_attribute(self):
        path = Path('@foo')
        self.assertEqual('', path.select(XML('<root/>')).render())
        self.assertEqual('bar', path.select(XML('<root foo="bar"/>')).render())

    def test_2step(self):
        xml = XML('<root><foo/><bar/></root>')
        self.assertEqual('<foo/><bar/>', Path('root/*').select(xml).render())
        self.assertEqual('<bar/>', Path('root/bar').select(xml).render())
        self.assertEqual('', Path('root/baz').select(xml).render())

    def test_2step_complex(self):
        xml = XML('<root><foo><bar/></foo></root>')
        self.assertEqual('<bar/>', Path('foo/bar').select(xml).render())
        self.assertEqual('<bar/>', Path('foo/*').select(xml).render())
        self.assertEqual('', Path('root/bar').select(xml).render())

        xml = XML('<root><foo><bar id="1"/></foo><bar id="2"/></root>')
        self.assertEqual('<bar id="2"/>', Path('root/bar').select(xml).render())

    def test_2step_text(self):
        xml = XML('<root><item>Foo</item></root>')
        self.assertEqual('Foo', Path('item/text()').select(xml).render())
        xml = XML('<root><item>Foo</item><item>Bar</item></root>')
        self.assertEqual('FooBar', Path('item/text()').select(xml).render())

    def test_3step(self):
        xml = XML('<root><foo><bar/></foo></root>')
        self.assertEqual('<bar/>', Path('root/foo/*').select(xml).render())

    def test_3step_complex(self):
        xml = XML('<root><foo><bar/></foo></root>')
        self.assertEqual('<bar/>', Path('root/*/bar').select(xml).render())
        xml = XML('<root><foo><bar id="1"/></foo><bar id="2"/></root>')
        self.assertEqual('<bar id="1"/><bar id="2"/>',
                         Path('root//bar').select(xml).render())

    def test_predicate_attr(self):
        xml = XML('<root><item/><item important="very"/></root>')
        self.assertEqual('<item important="very"/>',
                         Path('root/item[@important]').select(xml).render())
        self.assertEqual('<item important="very"/>',
                         Path('root/item[@important="very"]').select(xml).render())

        xml = XML('<root><item/><item important="notso"/></root>')
        self.assertEqual('',
                         Path('root/item[@important="very"]').select(xml).render())
        self.assertEqual('<item/><item important="notso"/>',
                         Path('root/item[@important!="very"]').select(xml).render())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(Path.__module__))
    suite.addTest(unittest.makeSuite(PathTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
