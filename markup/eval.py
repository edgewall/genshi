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
        self.code = _compile(source, filename, lineno)

    def __repr__(self):
        return '<Expression "%s">' % self.source

    def evaluate(self, data):
        """Evaluate the expression against the given data dictionary.
        
        @param data: a mapping containing the data to evaluate against
        @return: the result of the evaluation
        """
        retval = eval(self.code)
        if callable(retval):
            retval = retval()
        return retval


def _compile(source, filename=None, lineno=-1):
    tree = parse(source, 'eval')
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

def _lookup_name(data, name, locals=None):
    val = data.get(name)
    if val is None and locals:
        val = locals.get(name)
    if val is None:
        val = getattr(__builtin__, name, None)
    return val

def _lookup_attribute(data, obj, key):
    if hasattr(obj, key):
        return getattr(obj, key)
    try:
        return obj[key]
    except (KeyError, TypeError):
        return None

def _lookup_item(data, obj, key):
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

    def visit(self, node, *args, **kwargs):
        v = self._visitors.get(node.__class__)
        if not v:
            v = getattr(self, 'visit%s' % node.__class__.__name__)
            self._visitors[node.__class__] = v
        return v(node, *args, **kwargs)

    def visitExpression(self, node, *args, **kwargs):
        node.node = self.visit(node.node, *args, **kwargs)
        return node

    # Functions & Accessors

    def visitCallFunc(self, node, *args, **kwargs):
        node.node = self.visit(node.node, *args, **kwargs)
        node.args = map(lambda x: self.visit(x, *args, **kwargs), node.args)
        if node.star_args:
            node.star_args = map(lambda x: self.visit(x, *args, **kwargs),
                                 node.star_args)
        if node.dstar_args:
            node.dstart_args = map(lambda x: self.visit(x, *args, **kwargs),
                                   node.dstar_args)
        return node

    def visitGetattr(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        return node

    def visitSubscript(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        node.subs = map(lambda x: self.visit(x, *args, **kwargs), node.subs)
        return node

    # Operators

    def _visitBoolOp(self, node, *args, **kwargs):
        node.nodes = map(lambda x: self.visit(x, *args, **kwargs), node.nodes)
        return node
    visitAnd = visitOr = visitBitand = visitBitor = _visitBoolOp

    def _visitBinOp(self, node, *args, **kwargs):
        node.left = self.visit(node.left, *args, **kwargs)
        node.right = self.visit(node.right, *args, **kwargs)
        return node
    visitAdd = visitSub = _visitBinOp
    visitDiv = visitFloorDiv = visitMod = visitMul = visitPower = _visitBinOp
    visitLeftShift = visitRightShift = _visitBinOp

    def visitCompare(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        node.ops = map(lambda (op, n): (op, self.visit(n, *args, **kwargs)),
                       node.ops)
        return node

    def _visitUnaryOp(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        return node
    visitUnaryAdd = visitUnarySub = visitNot = visitInvert = _visitUnaryOp
    visitBackquote = _visitUnaryOp

    # Identifiers, Literals and Comprehensions

    def _visitDefault(self, node, *args, **kwargs):
        return node
    visitAssName = visitAssTuple = _visitDefault
    visitConst = visitName = _visitDefault

    def visitKeyword(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        return node

    def visitDict(self, node, *args, **kwargs):
        node.items = map(lambda (k, v): (self.visit(k, *args, **kwargs),
                                         self.visit(v, *args, **kwargs)),
                         node.items)
        return node

    def visitTuple(self, node, *args, **kwargs):
        node.nodes = map(lambda n: self.visit(n, *args, **kwargs), node.nodes)
        return node

    def visitList(self, node, *args, **kwargs):
        node.nodes = map(lambda n: self.visit(n, *args, **kwargs), node.nodes)
        return node

    def visitListComp(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        node.quals = map(lambda x: self.visit(x, *args, **kwargs), node.quals)
        return node

    def visitListCompFor(self, node, *args, **kwargs):
        node.assign = self.visit(node.assign, *args, **kwargs)
        node.list = self.visit(node.list, *args, **kwargs)
        node.ifs = map(lambda x: self.visit(x, *args, **kwargs), node.ifs)
        return node

    def visitListCompIf(self, node, *args, **kwargs):
        node.test = self.visit(node.test, *args, **kwargs)
        return node


class ExpressionASTTransformer(ASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for template expressions.
    """

    def visitGetattr(self, node, *args, **kwargs):
        return ast.CallFunc(ast.Name('_lookup_attribute'),
            [ast.Name('data'), self.visit(node.expr, *args, **kwargs),
             ast.Const(node.attrname)]
        )

    def visitListComp(self, node, *args, **kwargs):
        old_lookup_locals = kwargs.get('lookup_locals', False)
        kwargs['lookup_locals'] = True
        node.expr = self.visit(node.expr, *args, **kwargs)
        node.quals = map(lambda x: self.visit(x, *args, **kwargs), node.quals)
        kwargs['lookup_locals'] = old_lookup_locals
        return node

    def visitName(self, node, *args, **kwargs):
        func_args = [ast.Name('data'), ast.Const(node.name)]
        if kwargs.get('lookup_locals'):
            func_args.append(ast.CallFunc(ast.Name('locals'), []))
        return ast.CallFunc(ast.Name('_lookup_name'), func_args)
        return node

    def visitSubscript(self, node, *args, **kwargs):
        return ast.CallFunc(ast.Name('_lookup_item'),
            [ast.Name('data'), self.visit(node.expr, *args, **kwargs),
             ast.Tuple(map(self.visit, node.subs, *args, **kwargs))]
        )
