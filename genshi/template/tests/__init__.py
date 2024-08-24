# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
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

def suite():
    from genshi.template.tests import test_base, test_directives, test_eval, test_interpolation, \
                                      test_loader, test_markup, test_plugin, test_text
    suite = unittest.TestSuite()
    suite.addTest(test_base.suite())
    suite.addTest(test_directives.suite())
    suite.addTest(test_eval.suite())
    suite.addTest(test_interpolation.suite())
    suite.addTest(test_loader.suite())
    suite.addTest(test_markup.suite())
    suite.addTest(test_plugin.suite())
    suite.addTest(test_text.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
