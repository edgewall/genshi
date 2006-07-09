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
from HTMLParser import HTMLParseError
import unittest

from markup.builder import Element, tag
from markup.core import Stream


class ElementFactoryTestCase(unittest.TestCase):

    def test_link(self):
        link = tag.a(href='#', title='Foo', accesskey=None)('Bar')
        bits = iter(link.generate())
        self.assertEqual((Stream.START, ('a', [('href', "#"), ('title', "Foo")]),
                          (-1, -1)), bits.next())
        self.assertEqual((Stream.TEXT, u'Bar', (-1, -1)), bits.next())
        self.assertEqual((Stream.END, 'a', (-1, -1)), bits.next())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(Element.__module__))
    suite.addTest(unittest.makeSuite(ElementFactoryTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
