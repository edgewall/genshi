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

"""Support for "safe" evaluation of Python expressions."""

import __builtin__
import compiler
import operator

from markup.core import Stream

__all__ = ['Expression']


class Expression(object):
    """Evaluates Python expressions used in templates.

    >>> data = dict(test='Foo', items=[1, 2, 3], dict={'some': 'thing'})
    >>> Expression('test').evaluate(data)
    'Foo'
    >>> Expression('items[0]').evaluate(data)
    1
    >>> Expression('items[-1]').evaluate(data)
    3
    >>> Expression('dict["some"]').evaluate(data)
    'thing'
    
    Similar to e.g. Javascript, expressions in templates can use the dot
    notation for attribute access to access items in mappings:
    
    >>> Expression('dict.some').evaluate(data)
    'thing'
    
    This also works the other way around: item access can be used to access
    any object attribute (meaning there's no use for `getattr()` in templates):
    
    >>> class MyClass(object):
    ...     myattr = 'Bar'
    >>> data = dict(mine=MyClass(), key='myattr')
    >>> Expression('mine.myattr').evaluate(data)
    'Bar'
    >>> Expression('mine["myattr"]').evaluate(data)
    'Bar'
    >>> Expression('mine[key]').evaluate(data)
    'Bar'
    
    Most of the standard Python operators are also available to template
    expressions. Bitwise operators (including inversion and shifting) are not
    supported.
    
    >>> Expression('1 + 1').evaluate(data)
    2
    >>> Expression('3 - 1').evaluate(data)
    2
    >>> Expression('1 * 2').evaluate(data)
    2
    >>> Expression('4 / 2').evaluate(data)
    2
    >>> Expression('4 // 3').evaluate(data)
    1
    >>> Expression('4 % 3').evaluate(data)
    1
    >>> Expression('2 ** 3').evaluate(data)
    8
    >>> Expression('not True').evaluate(data)
    False
    >>> Expression('True and False').evaluate(data)
    False
    >>> Expression('True or False').evaluate(data)
    True
    >>> Expression('1 == 3').evaluate(data)
    False
    >>> Expression('1 != 3 == 3').evaluate(data)
    True
    >>> Expression('1 > 0').evaluate(data)
    True
    >>> Expression('True and "Foo"').evaluate(data)
    'Foo'
    >>> data = dict(items=[1, 2, 3])
    >>> Expression('2 in items').evaluate(data)
    True
    >>> Expression('not 2 in items').evaluate(data)
    False
    
    Built-in functions such as `len()` are also available in template
    expressions:
    
    >>> data = dict(items=[1, 2, 3])
    >>> Expression('len(items)').evaluate(data)
    3
    """
    __slots__ = ['source', 'ast']
    __visitors = {}

    def __init__(self, source):
        """Create the expression.
        
        @param source: the expression as string
        """
        self.source = source
        self.ast = None

    def evaluate(self, data):
        """Evaluate the expression against the given data dictionary.
        
        @param data: a mapping containing the data to evaluate against
        @return: the result of the evaluation
        """
        if not self.ast:
            self.ast = compiler.parse(self.source, 'eval')
        return self._visit(self.ast.node, data)

    def __repr__(self):
        return '<Expression "%s">' % self.source

    # AST traversal

    def _visit(self, node, data):
        v = self.__visitors.get(node.__class__)
        if not v:
            v = getattr(self, '_visit_%s' % node.__class__.__name__.lower())
            self.__visitors[node.__class__] = v
        return v(node, data)

    def _visit_expression(self, node, data):
        for child in node.getChildNodes():
            return self._visit(child, data)

    # Functions & Accessors

    def _visit_callfunc(self, node, data):
        func = self._visit(node.node, data)
        if func is None:
            return None
        args = [self._visit(arg, data) for arg in node.args
                if not isinstance(arg, compiler.ast.Keyword)]
        kwargs = dict([(arg.name, self._visit(arg.expr, data)) for arg
                       in node.args if isinstance(arg, compiler.ast.Keyword)])
        return func(*args, **kwargs)

    def _visit_getattr(self, node, data):
        obj = self._visit(node.expr, data)
        if hasattr(obj, node.attrname):
            return getattr(obj, node.attrname)
        try:
            return obj[node.attrname]
        except TypeError:
            return None

    def _visit_slice(self, node, data):
        obj = self._visit(node.expr, data)
        lower = node.lower and self._visit(node.lower, data) or None
        upper = node.upper and self._visit(node.upper, data) or None
        return obj[lower:upper]

    def _visit_subscript(self, node, data):
        obj = self._visit(node.expr, data)
        subs = map(lambda sub: self._visit(sub, data), node.subs)
        if len(subs) == 1:
            subs = subs[0]
        try:
            return obj[subs]
        except (KeyError, IndexError, TypeError):
            try:
                return getattr(obj, subs)
            except (AttributeError, TypeError):
                return None

    # Operators

    def _visit_and(self, node, data):
        return reduce(lambda x, y: x and y,
                      [self._visit(n, data) for n in node.nodes])

    def _visit_or(self, node, data):
        return reduce(lambda x, y: x or y,
                      [self._visit(n, data) for n in node.nodes])

    _OP_MAP = {'==': operator.eq, '!=': operator.ne,
               '<':  operator.lt, '<=': operator.le,
               '>':  operator.gt, '>=': operator.ge,
               'in': lambda x, y: operator.contains(y, x),
               'not in': lambda x, y: not operator.contains(y, x)}
    def _visit_compare(self, node, data):
        result = self._visit(node.expr, data)
        ops = node.ops[:]
        ops.reverse()
        for op, rval in ops:
            result = self._OP_MAP[op](result, self._visit(rval, data))
        return result

    def _visit_add(self, node, data):
        return self._visit(node.left, data) + self._visit(node.right, data)

    def _visit_div(self, node, data):
        return self._visit(node.left, data) / self._visit(node.right, data)

    def _visit_floordiv(self, node, data):
        return self._visit(node.left, data) // self._visit(node.right, data)

    def _visit_mod(self, node, data):
        return self._visit(node.left, data) % self._visit(node.right, data)

    def _visit_mul(self, node, data):
        return self._visit(node.left, data) * self._visit(node.right, data)

    def _visit_power(self, node, data):
        return self._visit(node.left, data) ** self._visit(node.right, data)

    def _visit_sub(self, node, data):
        return self._visit(node.left, data) - self._visit(node.right, data)

    def _visit_not(self, node, data):
        return not self._visit(node.expr, data)

    def _visit_unaryadd(self, node, data):
        return +self._visit(node.expr, data)

    def _visit_unarysub(self, node, data):
        return -self._visit(node.expr, data)

    # Identifiers & Literals

    def _visit_name(self, node, data):
        val = data.get(node.name)
        if val is None:
            val = getattr(__builtin__, node.name, None)
        return val

    def _visit_const(self, node, data):
        return node.value

    def _visit_dict(self, node, data):
        return dict([(self._visit(k, data), self._visit(v, data))
                     for k, v in node.items])

    def _visit_tuple(self, node, data):
        return tuple([self._visit(n, data) for n in node.nodes])

    def _visit_list(self, node, data):
        return [self._visit(n, data) for n in node.nodes]
