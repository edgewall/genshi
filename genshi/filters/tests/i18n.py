# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Edgewall Software
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
from StringIO import StringIO
import unittest

from genshi.template import MarkupTemplate
from genshi.filters.i18n import Translator


class TranslatorTestCase(unittest.TestCase):

    def test_extract_plural_form(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/">
          ${ngettext("Singular", "Plural", num)}
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual((2, 'ngettext', (u'Singular', u'Plural')), messages[0])

    def test_extract_included_attribute_text(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/">
          <span title="Foo"></span>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual((2, None, u'Foo'), messages[0])

    def test_extract_attribute_expr(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/">
          <input type="submit" value="${_('Save')}" />
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual((2, '_', u'Save'), messages[0])

    def test_extract_non_included_attribute_interpolated(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/">
          <a href="#anchor_${num}">Foo</a>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual((2, None, u'Foo'), messages[0])

    def test_extract_text_from_sub(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/">
          <py:if test="foo">Foo</py:if>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual((2, None, u'Foo'), messages[0])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TranslatorTestCase, 'test'))
    suite.addTests(doctest.DocTestSuite(Translator.__module__))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
