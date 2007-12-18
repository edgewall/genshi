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
import unittest

import genshi.filters.transform


def suite():
    from genshi.input import HTML
    from genshi.core import Markup
    from genshi.builder import tag
    suite = doctest.DocTestSuite(genshi.filters.transform,
                                 optionflags=doctest.NORMALIZE_WHITESPACE,
                                 extraglobs={'HTML': HTML, 'tag': tag,
                                     'Markup': Markup})
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
