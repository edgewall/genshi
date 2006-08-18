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
import new

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
        if isinstance(source, basestring):
            self.source = source
            if isinstance(source, unicode):
                source = '\xef\xbb\xbf' + source.encode('utf-8')
            self.code = _compile(parse(source, 'eval'), self.source,
                                 filename=filename, lineno=lineno)
        else:
            assert isinstance(source, ast.Node)
            self.source = '?'
            self.code = _compile(ast.Expression(source), filename=filename,
                                 lineno=lineno)

    def __repr__(self):
        return '<Expression "%s">' % self.source

    def evaluate(self, data, nocall=False):
        """Evaluate the expression against the given data dictionary.
        
        @param data: a mapping containing the data to evaluate against
        @param nocall: if true, the result of the evaluation is not called if
            if it is a callable
        @return: the result of the evaluation
        """
        retval = eval(self.code, {'data': data,
                                  '_lookup_name': _lookup_name,
                                  '_lookup_attr': _lookup_attr,
                                  '_lookup_item': _lookup_item})
        if not nocall and callable(retval):
            retval = retval()
        return retval


def _compile(node, source=None, filename=None, lineno=-1):
    tree = ExpressionASTTransformer().visit(node)
    if isinstance(filename, unicode):
        # unicode file names not allowed for code objects
        filename = filename.encode('utf-8', 'replace')
    elif not filename:
        filename = '<string>'
    tree.filename = filename
    if lineno <= 0:
        lineno = 1

    gen = ExpressionCodeGenerator(tree)
    gen.optimized = True
    code = gen.getCode()

    # We'd like to just set co_firstlineno, but it's readonly. So we need to
    # clone the code object while adjusting the line number
    return new.code(0, code.co_nlocals, code.co_stacksize,
                    code.co_flags | 0x0040, code.co_code, code.co_consts,
                    code.co_names, code.co_varnames, filename,
                    '<Expression %s>' % (repr(source).replace("'", '"') or '?'),
                    lineno, code.co_lnotab, (), ())

def _lookup_name(data, name, locals_=None):
    val = None
    if locals_:
        val = locals_.get(name)
    if val is None:
        val = data.get(name)
    if val is None:
        val = getattr(__builtin__, name, None)
    return val

def _lookup_attr(data, obj, key):
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

    def visitLambda(self, node, *args, **kwargs):
        node.code = self.visit(node.code, *args, **kwargs)
        node.filename = '<string>' # workaround for bug in pycodegen
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

    def visitGetattr(self, node, locals_=False):
        return ast.CallFunc(ast.Name('_lookup_attr'), [
            ast.Name('data'), self.visit(node.expr, locals_=locals_),
            ast.Const(node.attrname)
        ])

    def visitLambda(self, node, locals_=False):
        node.code = self.visit(node.code, locals_=True)
        node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def visitListComp(self, node, locals_=False):
        node.expr = self.visit(node.expr, locals_=True)
        node.quals = map(lambda x: self.visit(x, locals_=True), node.quals)
        return node

    def visitName(self, node, locals_=False):
        func_args = [ast.Name('data'), ast.Const(node.name)]
        if locals_:
            func_args.append(ast.CallFunc(ast.Name('locals'), []))
        return ast.CallFunc(ast.Name('_lookup_name'), func_args)

    def visitSubscript(self, node, locals_=False):
        return ast.CallFunc(ast.Name('_lookup_item'), [
            ast.Name('data'), self.visit(node.expr, locals_=locals_),
            ast.Tuple(map(lambda x: self.visit(x, locals_=locals_), node.subs))
        ])
