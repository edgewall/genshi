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

"""Support for "safe" evaluation of Python expressions."""

import __builtin__
from compiler import ast, parse
from compiler.pycodegen import ExpressionCodeGenerator

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
    
    All of the standard Python operators are available to template expressions.
    Built-in functions such as `len()` are also available in template
    expressions:
    
    >>> data = dict(items=[1, 2, 3])
    >>> Expression('len(items)').evaluate(data)
    3
    """
    __slots__ = ['source', 'code']

    def __init__(self, source, filename=None, lineno=-1):
        """Create the expression.
        
        @param source: the expression as string
        """
        self.source = source
        self.code = self._compile(source, filename, lineno)

    def __repr__(self):
        return '<Expression "%s">' % self.source

    def evaluate(self, data):
        """Evaluate the expression against the given data dictionary.
        
        @param data: a mapping containing the data to evaluate against
        @return: the result of the evaluation
        """
        return eval(self.code)

    def _compile(self, source, filename, lineno):
        tree = parse(self.source, 'eval')
        xform = ExpressionASTTransformer()
        tree = xform.visit(tree)

        if isinstance(filename, unicode):
            # pycodegen doesn't like unicode in the filename
            filename = filename.encode('utf-8', 'replace')
        tree.filename = filename or '<string>'

        gen = ExpressionCodeGenerator(tree)
        if lineno >= 0:
            gen.emit('SET_LINENO', lineno)

        return gen.getCode()

    def _lookup_name(self, data, name):
        val = data.get(name)
        if val is None:
            val = getattr(__builtin__, name, None)
        return val

    def _lookup_attribute(self, data, obj, key):
        if hasattr(obj, key):
            return getattr(obj, key)
        try:
            return obj[key]
        except (KeyError, TypeError):
            return None

    def _lookup_item(self, data, obj, key):
        if len(key) == 1:
            key = key[0]
        try:
            return obj[key]
        except (KeyError, IndexError, TypeError), e:
            pass
            if isinstance(key, basestring):
                try:
                    return getattr(obj, key)
                except (AttributeError, TypeError), e:
                    pass


class ASTTransformer(object):
    """General purpose base class for AST transformations.
    
    Every visitor method can be overridden to return an AST node that has been
    altered or replaced in some way.
    """
    _visitors = {}

    def visit(self, node):
        v = self._visitors.get(node.__class__)
        if not v:
            v = getattr(self, 'visit%s' % node.__class__.__name__)
            self._visitors[node.__class__] = v
        return v(node)

    def visitExpression(self, node):
        node.node = self.visit(node.node)
        return node

    # Functions & Accessors

    def visitCallFunc(self, node):
        node.node = self.visit(node.node)
        node.args = map(self.visit, node.args)
        if node.star_args:
            node.star_args = map(self.visit, node.star_args)
        if node.dstar_args:
            node.dstart_args = map(self.visit, node.dstar_args)
        return node

    def visitGetattr(self, node):
        node.expr = self.visit(node.expr)
        return node

    def visitSubscript(self, node):
        node.expr = self.visit(node.expr)
        node.subs = map(self.visit, node.subs)
        return node

    # Operators

    def _visitBoolOp(self, node):
        node.nodes = map(self.visit, node.nodes)
        return node
    visitAnd = visitOr = visitBitand = visitBitor = _visitBoolOp

    def _visitBinOp(self, node):
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        return node
    visitAdd = visitSub = _visitBinOp
    visitDiv = visitFloorDiv = visitMod = visitMul = visitPower = _visitBinOp
    visitLeftShift = visitRightShift = _visitBinOp

    def visitCompare(self, node):
        node.expr = self.visit(node.expr)
        node.ops = map(lambda (op, expr): (op, self.visit(expr)),
                       node.ops)
        return node

    def _visitUnaryOp(self, node):
        node.expr = self.visit(node.expr)
        return node
    visitUnaryAdd = visitUnarySub = visitNot = visitInvert = _visitUnaryOp

    # Identifiers & Literals

    def _visitDefault(self, node):
        return node
    visitConst = visitKeyword = visitName = _visitDefault

    def visitDict(self, node):
        node.items = map(lambda (k, v): (self.visit(k), self.visit(v)),
                         node.items)
        return node

    def visitTuple(self, node):
        node.nodes = map(lambda n: self.visit(n), node.nodes)
        return node

    def visitList(self, node):
        node.nodes = map(lambda n: self.visit(n), node.nodes)
        return node


class ExpressionASTTransformer(ASTTransformer):
    """Concrete AST transformer that implementations the AST transformations
    needed for template expressions.
    """

    def visitGetattr(self, node):
        return ast.CallFunc(
            ast.Getattr(ast.Name('self'), '_lookup_attribute'),
            [ast.Name('data'), self.visit(node.expr), ast.Const(node.attrname)]
        )

    def visitName(self, node):
        return ast.CallFunc(
            ast.Getattr(ast.Name('self'), '_lookup_name'),
            [ast.Name('data'), ast.Const(node.name)]
        )
        return node

    def visitSubscript(self, node):
        return ast.CallFunc(
            ast.Getattr(ast.Name('self'), '_lookup_item'),
            [ast.Name('data'), self.visit(node.expr),
             ast.Tuple(map(self.visit, node.subs))]
        )
