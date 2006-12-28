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

from genshi.template.text import TextTemplate


class TextTemplateTestCase(unittest.TestCase):
    """Tests for text template processing."""

    def test_escaping(self):
        tmpl = TextTemplate('\\#escaped')
        self.assertEqual('#escaped', str(tmpl.generate()))

    def test_comment(self):
        tmpl = TextTemplate('## a comment')
        self.assertEqual('', str(tmpl.generate()))

    def test_comment_escaping(self):
        tmpl = TextTemplate('\\## escaped comment')
        self.assertEqual('## escaped comment', str(tmpl.generate()))

    def test_end_with_args(self):
        tmpl = TextTemplate("""
        #if foo
          bar
        #end 'if foo'""")
        self.assertEqual('\n', str(tmpl.generate()))

    def test_latin1_encoded(self):
        text = u'$foo\xf6$bar'.encode('iso-8859-1')
        tmpl = TextTemplate(text, encoding='iso-8859-1')
        self.assertEqual(u'x\xf6y', unicode(tmpl.generate(foo='x', bar='y')))

    def test_empty_lines1(self):
        tmpl = TextTemplate("""Your items:

        #for item in items
          * ${item}
        #end""")
        self.assertEqual("""Your items:

          * 0
          * 1
          * 2
""", tmpl.generate(items=range(3)).render('text'))

    def test_empty_lines2(self):
        tmpl = TextTemplate("""Your items:

        #for item in items
          * ${item}

        #end""")
        self.assertEqual("""Your items:

          * 0

          * 1

          * 2

""", tmpl.generate(items=range(3)).render('text'))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(TextTemplate.__module__))
    suite.addTest(unittest.makeSuite(TextTemplateTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
