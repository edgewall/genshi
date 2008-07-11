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

from genshi.template.base import BadDirectiveError, TemplateSyntaxError
from genshi.template.markup import MarkupTemplate


def _unopt(code):
    return code.replace(' py:optimize=""', '')

class OptimizedTemplatesTestCase(unittest.TestCase):

    def _test_doc(self, doc, serializer='xml'):
        unopt = MarkupTemplate(XML(_unopt(doc)), serializer=serializer)
        optimizer = Optimizer(10)
        opt = MarkupTemplate(XML(doc), serializer=serializer,
                                optimizer=optimizer)
        result = unopt.generate().render()
        #non-cached one
        self.assertEqual(opt.generate().render(), result)
        #cached one
        self.assertEqual(opt.generate().render(), result)
    def test_double_match(self):
        code = """\
<root xmlns:py="http://genshi.edgewall.org/">
    <py:match path="tag/test">
        <other>
            ${select('.')}
        </other>
        <foo py:optimize="">
            Some text that could <b>be</b> optimized.
        </foo>
    </py:match>
    <py:match path="tag/other/test">
        <other>
            ${select('.')}
        </other>
    </py:match>
    <tag>
        <test py:optimize="">
            Foo bar <i>bar</i>
        </test>
    </tag>
</root>
"""
        self._test_doc(code)



def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(OptimizedTemplatesTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
