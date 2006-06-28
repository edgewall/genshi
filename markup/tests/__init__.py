# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://markup.cmlenz.net/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://markup.cmlenz.net/log/.

import doctest
import unittest

def suite():
    import markup
    from markup.tests import builder, core, eval, input, output, path, template
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(markup))
    suite.addTest(builder.suite())
    suite.addTest(core.suite())
    suite.addTest(eval.suite())
    suite.addTest(input.suite())
    suite.addTest(output.suite())
    suite.addTest(path.suite())
    suite.addTest(template.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
