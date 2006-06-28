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
# history and logs, available at hhttp://markup.cmlenz.net/log/.

import doctest
import unittest

from markup.eval import Expression


class ExpressionTestCase(unittest.TestCase):

    def test_str_literal(self):
        self.assertEqual('foo', Expression('"foo"').evaluate({}))
        self.assertEqual('foo', Expression('"""foo"""').evaluate({}))
        self.assertEqual('foo', Expression("'foo'").evaluate({}))
        self.assertEqual('foo', Expression("'''foo'''").evaluate({}))
        self.assertEqual('foo', Expression("u'foo'").evaluate({}))
        self.assertEqual('foo', Expression("r'foo'").evaluate({}))

    def test_num_literal(self):
        self.assertEqual(42, Expression("42").evaluate({}))
        self.assertEqual(42L, Expression("42L").evaluate({}))
        self.assertEqual(.42, Expression(".42").evaluate({}))
        self.assertEqual(07, Expression("07").evaluate({}))
        self.assertEqual(0xF2, Expression("0xF2").evaluate({}))
        self.assertEqual(0XF2, Expression("0XF2").evaluate({}))

    def test_dict_literal(self):
        self.assertEqual({}, Expression("{}").evaluate({}))
        self.assertEqual({'key': True},
                         Expression("{'key': value}").evaluate({'value': True}))

    def test_list_literal(self):
        self.assertEqual([], Expression("[]").evaluate({}))
        self.assertEqual([1, 2, 3], Expression("[1, 2, 3]").evaluate({}))
        self.assertEqual([True],
                         Expression("[value]").evaluate({'value': True}))

    def test_tuple_literal(self):
        self.assertEqual((), Expression("()").evaluate({}))
        self.assertEqual((1, 2, 3), Expression("(1, 2, 3)").evaluate({}))
        self.assertEqual((True,),
                         Expression("(value,)").evaluate({'value': True}))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ExpressionTestCase, 'test'))
    suite.addTest(doctest.DocTestSuite(Expression.__module__))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
