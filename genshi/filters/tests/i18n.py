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
from genshi.filters.i18n import Translator, extract


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

    def test_ignore_tag_with_fixed_xml_lang(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/">
          <p xml:lang="en">(c) 2007 Edgewall Software</p>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(0, len(messages))

    def test_extract_tag_with_variable_xml_lang(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/">
          <p xml:lang="${lang}">(c) 2007 Edgewall Software</p>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual((2, None, u'(c) 2007 Edgewall Software'), messages[0])

    def test_ignore_attribute_with_expression(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/">
          <input type="submit" value="Reply" title="Reply to comment $num" />
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(0, len(messages))

    def test_extract_i18n_msg(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Please see <a href="help.html">Help</a> for details.
          </p>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual('Please see [1:Help] for details.', messages[0][2])

    def test_translate_i18n_msg(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Please see <a href="help.html">Help</a> for details.
          </p>
        </html>""")
        gettext = lambda s: u"Für Details siehe bitte [1:Hilfe]."
        tmpl.filters.insert(0, Translator(gettext))
        self.assertEqual("""<html>
          <p>Für Details siehe bitte <a href="help.html">Hilfe</a>.</p>
        </html>""", tmpl.generate().render())

    def test_extract_i18n_msg_nested(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Please see <a href="help.html"><em>Help</em> page</a> for details.
          </p>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual('Please see [1:[2:Help] page] for details.',
                         messages[0][2])

    def test_translate_i18n_msg_nested(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Please see <a href="help.html"><em>Help</em> page</a> for details.
          </p>
        </html>""")
        gettext = lambda s: u"Für Details siehe bitte [1:[2:Hilfeseite]]."
        tmpl.filters.insert(0, Translator(gettext))
        self.assertEqual("""<html>
          <p>Für Details siehe bitte <a href="help.html"><em>Hilfeseite</em></a>.</p>
        </html>""", tmpl.generate().render())

    def test_extract_i18n_msg_empty(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Show me <input type="text" name="num" /> entries per page.
          </p>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual('Show me [1:] entries per page.', messages[0][2])

    def test_translate_i18n_msg_empty(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Show me <input type="text" name="num" /> entries per page.
          </p>
        </html>""")
        gettext = lambda s: u"[1:] Einträge pro Seite anzeigen."
        tmpl.filters.insert(0, Translator(gettext))
        self.assertEqual("""<html>
          <p><input type="text" name="num"/> Einträge pro Seite anzeigen.</p>
        </html>""", tmpl.generate().render())

    def test_extract_i18n_msg_multiple(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Please see <a href="help.html">Help</a> for <em>details</em>.
          </p>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual('Please see [1:Help] for [2:details].', messages[0][2])

    def test_translate_i18n_msg_multiple(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Please see <a href="help.html">Help</a> for <em>details</em>.
          </p>
        </html>""")
        gettext = lambda s: u"Für [2:Details] siehe bitte [1:Hilfe]."
        tmpl.filters.insert(0, Translator(gettext))
        self.assertEqual("""<html>
          <p>Für <em>Details</em> siehe bitte <a href="help.html">Hilfe</a>.</p>
        </html>""", tmpl.generate().render())

    def test_extract_i18n_msg_multiple_empty(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Show me <input type="text" name="num" /> entries per page, starting at page <input type="text" name="num" />.
          </p>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual('Show me [1:] entries per page, starting at page [2:].',
                         messages[0][2])

    def test_translate_i18n_msg_multiple_empty(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Show me <input type="text" name="num" /> entries per page, starting at page <input type="text" name="num" />.
          </p>
        </html>""")
        gettext = lambda s: u"[1:] Einträge pro Seite, beginnend auf Seite [2:]."
        tmpl.filters.insert(0, Translator(gettext))
        self.assertEqual("""<html>
          <p><input type="text" name="num"/> Eintr\xc3\xa4ge pro Seite, beginnend auf Seite <input type="text" name="num"/>.</p>
        </html>""", tmpl.generate().render())

    def test_extract_i18n_msg_with_directive(self):
        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
            xmlns:i18n="http://genshi.edgewall.org/i18n">
          <p i18n:msg="">
            Show me <input type="text" name="num" py:attrs="{'value': x}" /> entries per page.
          </p>
        </html>""")
        translator = Translator()
        messages = list(translator.extract(tmpl.stream))
        self.assertEqual(1, len(messages))
        self.assertEqual('Show me [1:] entries per page.', messages[0][2])

    # FIXME: this currently fails :-/
#    def test_translate_i18n_msg_with_directive(self):
#        tmpl = MarkupTemplate("""<html xmlns:py="http://genshi.edgewall.org/"
#            xmlns:i18n="http://genshi.edgewall.org/i18n">
#          <p i18n:msg="">
#            Show me <input type="text" name="num" py:attrs="{'value': x}" /> entries per page.
#          </p>
#        </html>""")
#        gettext = lambda s: u"[1:] Einträge pro Seite anzeigen."
#        tmpl.filters.insert(0, Translator(gettext))
#        self.assertEqual("""<html>
#          <p><input type="text" name="num" value="x"/> Einträge pro Seite anzeigen.</p>
#        </html>""", tmpl.generate().render())


class ExtractTestCase(unittest.TestCase):

    def test_markup_template_extraction(self):
        buf = StringIO("""<html xmlns:py="http://genshi.edgewall.org/">
          <head>
            <title>Example</title>
          </head>
          <body>
            <h1>Example</h1>
            <p>${_("Hello, %(name)s") % dict(name=username)}</p>
            <p>${ngettext("You have %d item", "You have %d items", num)}</p>
          </body>
        </html>""")
        results = list(extract(buf, ['_', 'ngettext'], [], {}))
        self.assertEqual([
            (3, None, u'Example', []),
            (6, None, u'Example', []),
            (7, '_', u'Hello, %(name)s', []),
            (8, 'ngettext', (u'You have %d item', u'You have %d items'), []),
        ], results)

    def test_text_template_extraction(self):
        buf = StringIO("""${_("Dear %(name)s") % {'name': name}},
        
        ${ngettext("Your item:", "Your items", len(items))}
        #for item in items
         * $item
        #end
        
        All the best,
        Foobar""")
        results = list(extract(buf, ['_', 'ngettext'], [], {
            'template_class': 'genshi.template:TextTemplate'
        }))
        self.assertEqual([
            (1, '_', u'Dear %(name)s', []),
            (3, 'ngettext', (u'Your item:', u'Your items'), []),
            (7, None, u'All the best,\n        Foobar', [])
        ], results)

    def test_extraction_inside_ignored_tags(self):
        buf = StringIO("""<html xmlns:py="http://genshi.edgewall.org/">
          <script type="text/javascript">
            $('#llist').tabs({
              remote: true,
              spinner: "${_('Please wait...')}"
            });
          </script>
        </html>""")
        results = list(extract(buf, ['_'], [], {}))
        self.assertEqual([
            (5, '_', u'Please wait...', []),
        ], results)

    def test_extraction_inside_ignored_tags_with_directives(self):
        buf = StringIO("""<html xmlns:py="http://genshi.edgewall.org/">
          <script type="text/javascript">
            <py:if test="foobar">
              alert("This shouldn't be extracted");
            </py:if>
          </script>
        </html>""")
        self.assertEqual([], list(extract(buf, ['_'], [], {})))


def suite():
    suite = unittest.TestSuite()
    suite.addTests(doctest.DocTestSuite(Translator.__module__))
    suite.addTest(unittest.makeSuite(TranslatorTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ExtractTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
