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
import sys

from markup.core import Stream
from markup.output import DocType, XMLSerializer


class XMLSerializerTestCase(unittest.TestCase):

    def test_doctype_in_stream(self):
        stream = Stream([(Stream.DOCTYPE, DocType.HTML_STRICT, ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_in_stream_no_sysid(self):
        stream = Stream([(Stream.DOCTYPE,
                         ('html', '-//W3C//DTD HTML 4.01//EN', None),
                         ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">\n',
                         output)

    def test_doctype_in_stream_no_pubid(self):
        stream = Stream([(Stream.DOCTYPE,
                         ('html', None, 'http://www.w3.org/TR/html4/strict.dtd'),
                         ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!DOCTYPE html SYSTEM '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_in_stream_no_pubid_or_sysid(self):
        stream = Stream([(Stream.DOCTYPE, ('html', None, None),
                         ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!DOCTYPE html>\n', output)

    def test_serializer_doctype(self):
        stream = Stream([])
        output = stream.render(XMLSerializer, doctype=DocType.HTML_STRICT)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_one_and_only(self):
        stream = Stream([(Stream.DOCTYPE, ('html', None, None), ('?', -1, -1))])
        output = stream.render(XMLSerializer, doctype=DocType.HTML_STRICT)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_comment(self):
        stream = Stream([(Stream.COMMENT, 'foo bar', ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!--foo bar-->', output)

    def test_processing_instruction(self):
        stream = Stream([(Stream.PI, ('python', 'x = 2'), ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<?python x = 2?>', output)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(XMLSerializerTestCase, 'test'))
    suite.addTest(doctest.DocTestSuite(XMLSerializer.__module__))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
