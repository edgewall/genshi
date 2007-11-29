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

import unittest

from genshi.template import MarkupTemplate


exploit_template = MarkupTemplate(u'''\
<html xmlns:py="http://genshi.edgewall.org/">
  <div py:content="(23).__class__.__base__"/>
  <p>${(42).__class__.__base__}</p>
</html>
''', lookup='lenient', restricted=True)


class RestrictionsTestCase(unittest.TestCase):

    def test_various_exploits(self):
        self.assertEqual(exploit_template.generate().render('html'),
                         '<html>\n  <div></div>\n  <p></p>\n</html>')

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RestrictionsTestCase, 'test'))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
