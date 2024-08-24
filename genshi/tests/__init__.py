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

def suite():
    import genshi
    from genshi.tests import test_builder, test_core, test_input, test_output, test_path, test_util
    from genshi.filters import tests as filters
    from genshi.template import tests as template

    suite = unittest.TestSuite()
    suite.addTest(test_builder.suite())
    suite.addTest(test_core.suite())
    suite.addTest(filters.suite())
    suite.addTest(test_input.suite())
    suite.addTest(test_output.suite())
    suite.addTest(test_path.suite())
    suite.addTest(template.suite())
    suite.addTest(test_util.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
