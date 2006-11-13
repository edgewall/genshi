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


def suite():
    from genshi.template.tests import core, directives, eval, loader, markup, \
                                      plugin, text
    suite = unittest.TestSuite()
    suite.addTest(core.suite())
    suite.addTest(directives.suite())
    suite.addTest(eval.suite())
    suite.addTest(loader.suite())
    suite.addTest(markup.suite())
    suite.addTest(plugin.suite())
    suite.addTest(text.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
