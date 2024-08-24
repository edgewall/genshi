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

import unittest

from genshi.core import Attrs, Markup, QName, Stream
from genshi.input import HTML, XML
from genshi.output import DocType, XMLSerializer, XHTMLSerializer, \
                          HTMLSerializer, EmptyTagFilter
from genshi.tests.utils import doctest_suite


class XMLSerializerTestCase(unittest.TestCase):

    def test_with_xml_decl(self):
        stream = Stream([(Stream.XML_DECL, ('1.0', None, -1), (None, -1, -1))])
        output = stream.render(XMLSerializer, doctype='xhtml', encoding=None)
        self.assertEqual('<?xml version="1.0"?>\n'
                         '<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD XHTML 1.0 Strict//EN" '
                         '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n',
                         output)

    def test_doctype_in_stream(self):
        stream = Stream([(Stream.DOCTYPE, DocType.HTML_STRICT, (None, -1, -1))])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_in_stream_no_sysid(self):
        stream = Stream([(Stream.DOCTYPE,
                         ('html', '-//W3C//DTD HTML 4.01//EN', None),
                         (None, -1, -1))])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">\n',
                         output)

    def test_doctype_in_stream_no_pubid(self):
        stream = Stream([
            (Stream.DOCTYPE,
             ('html', None, 'http://www.w3.org/TR/html4/strict.dtd'),
             (None, -1, -1))
        ])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual('<!DOCTYPE html SYSTEM '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_in_stream_no_pubid_or_sysid(self):
        stream = Stream([(Stream.DOCTYPE, ('html', None, None),
                         (None, -1, -1))])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual('<!DOCTYPE html>\n', output)

    def test_serializer_doctype(self):
        stream = Stream([])
        output = stream.render(XMLSerializer, doctype=DocType.HTML_STRICT,
                               encoding=None)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_one_and_only(self):
        stream = Stream([
            (Stream.DOCTYPE, ('html', None, None), (None, -1, -1))
        ])
        output = stream.render(XMLSerializer, doctype=DocType.HTML_STRICT,
                               encoding=None)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_comment(self):
        stream = Stream([(Stream.COMMENT, 'foo bar', (None, -1, -1))])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual('<!--foo bar-->', output)

    def test_processing_instruction(self):
        stream = Stream([(Stream.PI, ('python', 'x = 2'), (None, -1, -1))])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual('<?python x = 2?>', output)

    def test_nested_default_namespaces(self):
        stream = Stream([
            (Stream.START_NS, ('', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}div'), Attrs()), (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('http://example.org/}p'), (None, -1, -1)),
            (Stream.END_NS, '', (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('http://example.org/}p'), (None, -1, -1)),
            (Stream.END_NS, '', (None, -1, -1)),
            (Stream.TEXT, '\n        ', (None, -1, -1)),
            (Stream.END, QName('http://example.org/}div'), (None, -1, -1)),
            (Stream.END_NS, '', (None, -1, -1))
        ])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual("""<div xmlns="http://example.org/">
          <p/>
          <p/>
        </div>""", output)

    def test_nested_bound_namespaces(self):
        stream = Stream([
            (Stream.START_NS, ('x', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}div'), Attrs()), (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('x', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('http://example.org/}p'), (None, -1, -1)),
            (Stream.END_NS, 'x', (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('x', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('http://example.org/}p'), (None, -1, -1)),
            (Stream.END_NS, 'x', (None, -1, -1)),
            (Stream.TEXT, '\n        ', (None, -1, -1)),
            (Stream.END, QName('http://example.org/}div'), (None, -1, -1)),
            (Stream.END_NS, 'x', (None, -1, -1))
        ])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual("""<x:div xmlns:x="http://example.org/">
          <x:p/>
          <x:p/>
        </x:div>""", output)

    def test_multiple_default_namespaces(self):
        stream = Stream([
            (Stream.START, (QName('div'), Attrs()), (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('http://example.org/}p'), (None, -1, -1)),
            (Stream.END_NS, '', (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('http://example.org/}p'), (None, -1, -1)),
            (Stream.END_NS, '', (None, -1, -1)),
            (Stream.TEXT, '\n        ', (None, -1, -1)),
            (Stream.END, QName('div'), (None, -1, -1)),
        ])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual("""<div>
          <p xmlns="http://example.org/"/>
          <p xmlns="http://example.org/"/>
        </div>""", output)

    def test_multiple_bound_namespaces(self):
        stream = Stream([
            (Stream.START, (QName('div'), Attrs()), (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('x', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('http://example.org/}p'), (None, -1, -1)),
            (Stream.END_NS, 'x', (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('x', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('http://example.org/}p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('http://example.org/}p'), (None, -1, -1)),
            (Stream.END_NS, 'x', (None, -1, -1)),
            (Stream.TEXT, '\n        ', (None, -1, -1)),
            (Stream.END, QName('div'), (None, -1, -1)),
        ])
        output = stream.render(XMLSerializer, encoding=None)
        self.assertEqual("""<div>
          <x:p xmlns:x="http://example.org/"/>
          <x:p xmlns:x="http://example.org/"/>
        </div>""", output)

    def test_atom_with_xhtml(self):
        text = """<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en">
            <id>urn:uuid:c60843aa-0da8-4fa6-bbe5-98007bc6774e</id>
            <updated>2007-01-28T11:36:02.807108-06:00</updated>
            <title type="xhtml">
                <div xmlns="http://www.w3.org/1999/xhtml">Example</div>
            </title>
            <subtitle type="xhtml">
                <div xmlns="http://www.w3.org/1999/xhtml">Bla bla bla</div>
            </subtitle>
            <icon/>
        </feed>"""
        output = XML(text).render(XMLSerializer, encoding=None)
        self.assertEqual(text, output)


class XHTMLSerializerTestCase(unittest.TestCase):

    def test_xml_decl_dropped(self):
        stream = Stream([(Stream.XML_DECL, ('1.0', None, -1), (None, -1, -1))])
        output = stream.render(XHTMLSerializer, doctype='xhtml', encoding=None)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD XHTML 1.0 Strict//EN" '
                         '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n',
                         output)

    def test_xml_decl_included(self):
        stream = Stream([(Stream.XML_DECL, ('1.0', None, -1), (None, -1, -1))])
        output = stream.render(XHTMLSerializer, doctype='xhtml',
                               drop_xml_decl=False, encoding=None)
        self.assertEqual('<?xml version="1.0"?>\n'
                         '<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD XHTML 1.0 Strict//EN" '
                         '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n',
                         output)

    def test_xml_lang(self):
        text = '<p xml:lang="en">English text</p>'
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual('<p lang="en" xml:lang="en">English text</p>', output)

    def test_xml_lang_nodup(self):
        text = '<p xml:lang="en" lang="en">English text</p>'
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual('<p xml:lang="en" lang="en">English text</p>', output)

    def test_textarea_whitespace(self):
        content = '\nHey there.  \n\n    I am indented.\n'
        stream = XML('<textarea name="foo">%s</textarea>' % content)
        output = stream.render(XHTMLSerializer, encoding=None)
        self.assertEqual('<textarea name="foo">%s</textarea>' % content, output)

    def test_pre_whitespace(self):
        content = '\nHey <em>there</em>.  \n\n    I am indented.\n'
        stream = XML('<pre>%s</pre>' % content)
        output = stream.render(XHTMLSerializer, encoding=None)
        self.assertEqual('<pre>%s</pre>' % content, output)

    def test_xml_space(self):
        text = '<foo xml:space="preserve"> Do not mess  \n\n with me </foo>'
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual('<foo> Do not mess  \n\n with me </foo>', output)

    def test_empty_script(self):
        text = """<html xmlns="http://www.w3.org/1999/xhtml">
            <script src="foo.js" />
        </html>"""
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual("""<html xmlns="http://www.w3.org/1999/xhtml">
            <script src="foo.js"></script>
        </html>""", output)

    def test_script_escaping(self):
        text = """<script>/*<![CDATA[*/
            if (1 < 2) { alert("Doh"); }
        /*]]>*/</script>"""
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual(text, output)

    def test_script_escaping_with_namespace(self):
        text = """<script xmlns="http://www.w3.org/1999/xhtml">/*<![CDATA[*/
            if (1 < 2) { alert("Doh"); }
        /*]]>*/</script>"""
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual(text, output)

    def test_style_escaping(self):
        text = """<style>/*<![CDATA[*/
            html > body { display: none; }
        /*]]>*/</style>"""
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual(text, output)

    def test_style_escaping_with_namespace(self):
        text = """<style xmlns="http://www.w3.org/1999/xhtml">/*<![CDATA[*/
            html > body { display: none; }
        /*]]>*/</style>"""
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual(text, output)

    def test_embedded_svg(self):
        text = """<html xmlns="http://www.w3.org/1999/xhtml" xmlns:svg="http://www.w3.org/2000/svg">
          <body>
            <button>
              <svg:svg width="600px" height="400px">
                <svg:polygon id="triangle" points="50,50 50,300 300,300"></svg:polygon>
              </svg:svg>
            </button>
          </body>
        </html>"""
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual(text, output)

    def test_xhtml_namespace_prefix(self):
        text = """<div xmlns="http://www.w3.org/1999/xhtml">
            <strong>Hello</strong>
        </div>"""
        output = XML(text).render(XHTMLSerializer, encoding=None)
        self.assertEqual(text, output)

    def test_nested_default_namespaces(self):
        stream = Stream([
            (Stream.START_NS, ('', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('div'), Attrs()), (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('p'), (None, -1, -1)),
            (Stream.END_NS, '', (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('p'), (None, -1, -1)),
            (Stream.END_NS, '', (None, -1, -1)),
            (Stream.TEXT, '\n        ', (None, -1, -1)),
            (Stream.END, QName('div'), (None, -1, -1)),
            (Stream.END_NS, '', (None, -1, -1))
        ])
        output = stream.render(XHTMLSerializer, encoding=None)
        self.assertEqual("""<div xmlns="http://example.org/">
          <p></p>
          <p></p>
        </div>""", output)

    def test_nested_bound_namespaces(self):
        stream = Stream([
            (Stream.START_NS, ('x', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('div'), Attrs()), (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('x', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('p'), (None, -1, -1)),
            (Stream.END_NS, 'x', (None, -1, -1)),
            (Stream.TEXT, '\n          ', (None, -1, -1)),
            (Stream.START_NS, ('x', 'http://example.org/'), (None, -1, -1)),
            (Stream.START, (QName('p'), Attrs()), (None, -1, -1)),
            (Stream.END, QName('p'), (None, -1, -1)),
            (Stream.END_NS, 'x', (None, -1, -1)),
            (Stream.TEXT, '\n        ', (None, -1, -1)),
            (Stream.END, QName('div'), (None, -1, -1)),
            (Stream.END_NS, 'x', (None, -1, -1))
        ])
        output = stream.render(XHTMLSerializer, encoding=None)
        self.assertEqual("""<div xmlns:x="http://example.org/">
          <p></p>
          <p></p>
        </div>""", output)

    def test_html5_doctype(self):
        stream = HTML(u'<html></html>')
        output = stream.render(XHTMLSerializer, doctype=DocType.HTML5,
                               encoding=None)
        self.assertEqual('<!DOCTYPE html>\n<html></html>', output)

    def test_ignorable_space(self):
        text = '<foo> Mess  \n\n\n with me!  </foo>'
        output = XML(text).render(XMLSerializer, encoding=None)
        self.assertEqual('<foo> Mess\n with me!  </foo>', output)

    def test_cache_markup(self):
        loc = (None, -1, -1)
        stream = Stream([(Stream.START, (QName('foo'), Attrs()), loc),
                         (Stream.TEXT, u'&hellip;', loc),
                         (Stream.END, QName('foo'), loc),
                         (Stream.START, (QName('bar'), Attrs()), loc),
                         (Stream.TEXT, Markup('&hellip;'), loc),
                         (Stream.END, QName('bar'), loc)])
        output = stream.render(XMLSerializer, encoding=None, 
                               strip_whitespace=False)
        self.assertEqual('<foo>&amp;hellip;</foo><bar>&hellip;</bar>', output)


class HTMLSerializerTestCase(unittest.TestCase):

    def test_xml_lang(self):
        text = '<p xml:lang="en">English text</p>'
        output = XML(text).render(HTMLSerializer, encoding=None)
        self.assertEqual('<p lang="en">English text</p>', output)

    def test_xml_lang_nodup(self):
        text = '<p lang="en" xml:lang="en">English text</p>'
        output = XML(text).render(HTMLSerializer, encoding=None)
        self.assertEqual('<p lang="en">English text</p>', output)

    def test_textarea_whitespace(self):
        content = '\nHey there.  \n\n    I am indented.\n'
        stream = XML('<textarea name="foo">%s</textarea>' % content)
        output = stream.render(HTMLSerializer, encoding=None)
        self.assertEqual('<textarea name="foo">%s</textarea>' % content, output)

    def test_pre_whitespace(self):
        content = '\nHey <em>there</em>.  \n\n    I am indented.\n'
        stream = XML('<pre>%s</pre>' % content)
        output = stream.render(HTMLSerializer, encoding=None)
        self.assertEqual('<pre>%s</pre>' % content, output)

    def test_xml_space(self):
        text = '<foo xml:space="preserve"> Do not mess  \n\n with me </foo>'
        output = XML(text).render(HTMLSerializer, encoding=None)
        self.assertEqual('<foo> Do not mess  \n\n with me </foo>', output)

    def test_empty_script(self):
        text = '<script src="foo.js" />'
        output = XML(text).render(HTMLSerializer, encoding=None)
        self.assertEqual('<script src="foo.js"></script>', output)

    def test_script_escaping(self):
        text = '<script>if (1 &lt; 2) { alert("Doh"); }</script>'
        output = XML(text).render(HTMLSerializer, encoding=None)
        self.assertEqual('<script>if (1 < 2) { alert("Doh"); }</script>',
                         output)

    def test_script_escaping_with_namespace(self):
        text = """<script xmlns="http://www.w3.org/1999/xhtml">
            if (1 &lt; 2) { alert("Doh"); }
        </script>"""
        output = XML(text).render(HTMLSerializer, encoding=None)
        self.assertEqual("""<script>
            if (1 < 2) { alert("Doh"); }
        </script>""", output)

    def test_style_escaping(self):
        text = '<style>html &gt; body { display: none; }</style>'
        output = XML(text).render(HTMLSerializer, encoding=None)
        self.assertEqual('<style>html > body { display: none; }</style>',
                         output)

    def test_style_escaping_with_namespace(self):
        text = """<style xmlns="http://www.w3.org/1999/xhtml">
            html &gt; body { display: none; }
        </style>"""
        output = XML(text).render(HTMLSerializer, encoding=None)
        self.assertEqual("""<style>
            html > body { display: none; }
        </style>""", output)

    def test_html5_doctype(self):
        stream = HTML(u'<html></html>')
        output = stream.render(HTMLSerializer, doctype=DocType.HTML5,
                               encoding=None)
        self.assertEqual('<!DOCTYPE html>\n<html></html>', output)


class EmptyTagFilterTestCase(unittest.TestCase):

    def test_empty(self):
        stream = XML('<elem></elem>') | EmptyTagFilter()
        self.assertEqual([EmptyTagFilter.EMPTY], [ev[0] for ev in stream])

    def test_text_content(self):
        stream = XML('<elem>foo</elem>') | EmptyTagFilter()
        self.assertEqual([Stream.START, Stream.TEXT, Stream.END],
                         [ev[0] for ev in stream])

    def test_elem_content(self):
        stream = XML('<elem><sub /><sub /></elem>') | EmptyTagFilter()
        self.assertEqual([Stream.START, EmptyTagFilter.EMPTY,
                          EmptyTagFilter.EMPTY, Stream.END],
                         [ev[0] for ev in stream])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(XMLSerializerTestCase))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(XHTMLSerializerTestCase))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(HTMLSerializerTestCase))
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(EmptyTagFilterTestCase))
    suite.addTest(doctest_suite(XMLSerializer.__module__))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
