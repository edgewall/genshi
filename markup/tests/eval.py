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
# history and logs, available at hhttp://markup.edgewall.org/log/.

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

    def test_unaryop_pos(self):
        self.assertEqual(1, Expression("+1").evaluate({}))
        self.assertEqual(1, Expression("+x").evaluate({'x': 1}))

    def test_unaryop_neg(self):
        self.assertEqual(-1, Expression("-1").evaluate({}))
        self.assertEqual(-1, Expression("-x").evaluate({'x': 1}))

    def test_unaryop_not(self):
        self.assertEqual(False, Expression("not True").evaluate({}))
        self.assertEqual(False, Expression("not x").evaluate({'x': True}))

    def test_unaryop_inv(self):
        self.assertEqual(-2, Expression("~1").evaluate({}))
        self.assertEqual(-2, Expression("~x").evaluate({'x': 1}))

    def test_binop_add(self):
        self.assertEqual(3, Expression("2 + 1").evaluate({}))
        self.assertEqual(3, Expression("x + y").evaluate({'x': 2, 'y': 1}))

    def test_binop_sub(self):
        self.assertEqual(1, Expression("2 - 1").evaluate({}))
        self.assertEqual(1, Expression("x - y").evaluate({'x': 1, 'y': 1}))

    def test_binop_sub(self):
        self.assertEqual(1, Expression("2 - 1").evaluate({}))
        self.assertEqual(1, Expression("x - y").evaluate({'x': 2, 'y': 1}))

    def test_binop_mul(self):
        self.assertEqual(4, Expression("2 * 2").evaluate({}))
        self.assertEqual(4, Expression("x * y").evaluate({'x': 2, 'y': 2}))

    def test_binop_pow(self):
        self.assertEqual(4, Expression("2 ** 2").evaluate({}))
        self.assertEqual(4, Expression("x ** y").evaluate({'x': 2, 'y': 2}))

    def test_binop_div(self):
        self.assertEqual(2, Expression("4 / 2").evaluate({}))
        self.assertEqual(2, Expression("x / y").evaluate({'x': 4, 'y': 2}))

    def test_binop_floordiv(self):
        self.assertEqual(1, Expression("3 // 2").evaluate({}))
        self.assertEqual(1, Expression("x // y").evaluate({'x': 3, 'y': 2}))

    def test_binop_mod(self):
        self.assertEqual(1, Expression("3 % 2").evaluate({}))
        self.assertEqual(1, Expression("x % y").evaluate({'x': 3, 'y': 2}))

    def test_binop_and(self):
        self.assertEqual(0, Expression("1 & 0").evaluate({}))
        self.assertEqual(0, Expression("x & y").evaluate({'x': 1, 'y': 0}))

    def test_binop_or(self):
        self.assertEqual(1, Expression("1 | 0").evaluate({}))
        self.assertEqual(1, Expression("x | y").evaluate({'x': 1, 'y': 0}))

    def test_binop_contains(self):
        self.assertEqual(True, Expression("1 in (1, 2, 3)").evaluate({}))
        self.assertEqual(True, Expression("x in y").evaluate({'x': 1,
                                                              'y': (1, 2, 3)}))

    def test_binop_not_contains(self):
        self.assertEqual(True, Expression("4 not in (1, 2, 3)").evaluate({}))
        self.assertEqual(True, Expression("x not in y").evaluate({'x': 4,
                                                                  'y': (1, 2, 3)}))

    def test_binop_is(self):
        self.assertEqual(True, Expression("1 is 1").evaluate({}))
        self.assertEqual(True, Expression("x is y").evaluate({'x': 1, 'y': 1}))
        self.assertEqual(False, Expression("1 is 2").evaluate({}))
        self.assertEqual(False, Expression("x is y").evaluate({'x': 1, 'y': 2}))

    def test_binop_is_not(self):
        self.assertEqual(True, Expression("1 is not 2").evaluate({}))
        self.assertEqual(True, Expression("x is not y").evaluate({'x': 1,
                                                                  'y': 2}))
        self.assertEqual(False, Expression("1 is not 1").evaluate({}))
        self.assertEqual(False, Expression("x is not y").evaluate({'x': 1,
                                                                   'y': 1}))

    def test_boolop_and(self):
        self.assertEqual(False, Expression("True and False").evaluate({}))
        self.assertEqual(False, Expression("x and y").evaluate({'x': True,
                                                                'y': False}))

    def test_boolop_or(self):
        self.assertEqual(True, Expression("True or False").evaluate({}))
        self.assertEqual(True, Expression("x or y").evaluate({'x': True,
                                                              'y': False}))

    def test_compare_eq(self):
        self.assertEqual(True, Expression("1 == 1").evaluate({}))
        self.assertEqual(True, Expression("x == y").evaluate({'x': 1, 'y': 1}))

    def test_compare_ne(self):
        self.assertEqual(False, Expression("1 != 1").evaluate({}))
        self.assertEqual(False, Expression("x != y").evaluate({'x': 1, 'y': 1}))
        self.assertEqual(False, Expression("1 <> 1").evaluate({}))
        self.assertEqual(False, Expression("x <> y").evaluate({'x': 1, 'y': 1}))

    def test_compare_lt(self):
        self.assertEqual(True, Expression("1 < 2").evaluate({}))
        self.assertEqual(True, Expression("x < y").evaluate({'x': 1, 'y': 2}))

    def test_compare_le(self):
        self.assertEqual(True, Expression("1 <= 1").evaluate({}))
        self.assertEqual(True, Expression("x <= y").evaluate({'x': 1, 'y': 1}))

    def test_compare_gt(self):
        self.assertEqual(True, Expression("2 > 1").evaluate({}))
        self.assertEqual(True, Expression("x > y").evaluate({'x': 2, 'y': 1}))

    def test_compare_ge(self):
        self.assertEqual(True, Expression("1 >= 1").evaluate({}))
        self.assertEqual(True, Expression("x >= y").evaluate({'x': 1, 'y': 1}))

    def test_compare_multi(self):
        self.assertEqual(True, Expression("1 != 3 == 3").evaluate({}))
        self.assertEqual(True, Expression("x != y == y").evaluate({'x': 1,
                                                                   'y': 3}))

    def test_call_function(self):
        self.assertEqual(42, Expression("foo()").evaluate({'foo': lambda: 42}))
        data = {'foo': 'bar'}
        self.assertEqual('BAR', Expression("foo.upper()").evaluate(data))
        data = {'foo': {'bar': range(42)}}
        self.assertEqual(42, Expression("len(foo.bar)").evaluate(data))

    # FIXME: need support for local names in comprehensions
    #def test_list_comprehension(self):
    #    expr = Expression("[n for n in numbers if n < 2]")
    #    self.assertEqual([0, 1], expr.evaluate({'numbers': range(5)}))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ExpressionTestCase, 'test'))
    suite.addTest(doctest.DocTestSuite(Expression.__module__))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
