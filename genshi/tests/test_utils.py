# -*- coding: utf-8 -*-

import doctest
import re
import sys

# copied from couchdb-python (3-clause BSD)
#   https://github.com/djc/couchdb-python/blob/8336362eda12e101643b9da7560a78723613d994/couchdb/tests/testutil.py
class Py23DocChecker(doctest.OutputChecker):
    def check_output(self, want, got, optionflags):
        if sys.version_info < (3, 0):
            got = re.sub("u'(.*?)'", "'\\1'", got)
        return doctest.OutputChecker.check_output(self, want, got, optionflags)

def doctest_suite(module, **kwargs):
    return doctest.DocTestSuite(module, checker=Py23DocChecker(), **kwargs)


