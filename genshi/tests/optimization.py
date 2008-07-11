# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 Edgewall Software
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
import sys

from genshi.core import Attrs, Stream, QName
from genshi.input import HTML, XML
from genshi.output import DocType, XMLSerializer, XHTMLSerializer, \
                          HTMLSerializer, EmptyTagFilter
from genshi.optimization import Optimizer, OptimizedFragment, OPTIMIZED_FRAGMENT

class FiltersOptimizationTestCase(unittest.TestCase):

    def _inner_helper(self, istream):
        optimizer = Optimizer(10)
        of = OptimizedFragment(istream, optimizer, 1, 0)
        stream = Stream([(OPTIMIZED_FRAGMENT, of, (None, -1, -1))])
        return stream

    def _test_doc(self, doc, serializer):
        istream = XML(doc)
        istream = Stream(list(istream), serializer)
        stream = self._inner_helper(istream)
        #non-cached one
        self.assertEqual(stream.render(), istream.render())
        #cached one
        self.assertEqual(stream.render(), istream.render())

    test_doc = """\
<div>
  <head>
    <title>Hello world</title>
    <style type="text/css">@import(style.css)</style>
  </head>
  <div>
    Hello everyone!
  </div>
  <span class="greeting">
        And you too!
  </span>
</div>
"""
    def test_xml_serializer(self):
        self._test_doc(self.test_doc, XMLSerializer())
    def test_xhtml_serializer(self):
        self._test_doc(self.test_doc, XHTMLSerializer())
    def test_html_serializer(self):
        self._test_doc(self.test_doc, HTMLSerializer())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FiltersOptimizationTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
