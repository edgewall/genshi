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

from markup import output

def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(output))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
