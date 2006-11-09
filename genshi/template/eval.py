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

"""Support for "safe" evaluation of Python expressions."""

import __builtin__
from compiler import ast, parse
from compiler.pycodegen import ExpressionCodeGenerator
import new

__all__ = ['Expression', 'Undefined']


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
        """Create the expression, either from a string, or from an AST node.
        
        @param source: either a string containing the source code of the
            expression, or an AST node
        @param filename: the (preferably absolute) name of the file containing
            the expression
        @param lineno: the number of the line on which the expression was found
        """
        if isinstance(source, basestring):
            self.source = source
            self.code = _compile(_parse(source), self.source, filename=filename,
                                 lineno=lineno)
        else:
            assert isinstance(source, ast.Node)
            self.source = '?'
            self.code = _compile(ast.Expression(source), filename=filename,
                                 lineno=lineno)

    def __eq__(self, other):
        return (type(other) == Expression) and (self.code == other.code)

    def __hash__(self):
        return hash(self.code)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return 'Expression(%r)' % self.source

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
                                  '_lookup_item': _lookup_item},
                                 {'data': data})
        if not nocall and type(retval) is not Undefined and callable(retval):
            retval = retval()
        return retval


class Undefined(object):
    """Represents a reference to an undefined variable.
    
    Unlike the Python runtime, template expressions can refer to an undefined
    variable without causing a `NameError` to be raised. The result will be an
    instance of the `Undefined´ class, which is treated the same as `False` in
    conditions, and acts as an empty collection in iterations:
    
    >>> foo = Undefined('foo')
    >>> bool(foo)
    False
    >>> list(foo)
    []
    >>> print foo
    undefined
    
    However, calling an undefined variable, or trying to access an attribute
    of that variable, will raise an exception that includes the name used to
    reference that undefined variable.
    
    >>> foo('bar')
    Traceback (most recent call last):
        ...
    NameError: Variable "foo" is not defined

    >>> foo.bar
    Traceback (most recent call last):
        ...
    NameError: Variable "foo" is not defined
    """
    __slots__ = ['_name']

    def __init__(self, name):
        self._name = name

    def __call__(self, *args, **kwargs):
        __traceback_hide__ = True
        self.throw()

    def __getattr__(self, name):
        __traceback_hide__ = True
        self.throw()

    def __iter__(self):
        return iter([])

    def __nonzero__(self):
        return False

    def __repr__(self):
        return 'undefined'

    def throw(self):
        __traceback_hide__ = True
        raise NameError('Variable "%s" is not defined' % self._name)


def _parse(source, mode='eval'):
    if isinstance(source, unicode):
        source = '\xef\xbb\xbf' + source.encode('utf-8')
    return parse(source, mode)

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
                    '<Expression %s>' % (repr(source or '?').replace("'", '"')),
                    lineno, code.co_lnotab, (), ())

BUILTINS = __builtin__.__dict__.copy()
BUILTINS['Undefined'] = Undefined

def _lookup_name(data, name, locals_=None):
    __traceback_hide__ = True
    val = Undefined
    if locals_:
        val = locals_.get(name, val)
    if val is Undefined:
        val = data.get(name, val)
        if val is Undefined:
            val = BUILTINS.get(name, val)
            if val is not Undefined or name == 'Undefined':
                return val
        else:
            return val
    else:
        return val
    return val(name)

def _lookup_attr(data, obj, key):
    __traceback_hide__ = True
    if type(obj) is Undefined:
        obj.throw()
    if hasattr(obj, key):
        return getattr(obj, key)
    try:
        return obj[key]
    except (KeyError, TypeError):
        return Undefined(key)

def _lookup_item(data, obj, key):
    __traceback_hide__ = True
    if type(obj) is Undefined:
        obj.throw()
    if len(key) == 1:
        key = key[0]
    try:
        return obj[key]
    except (KeyError, IndexError, TypeError), e:
        if isinstance(key, basestring):
            val = getattr(obj, key, Undefined)
            if val is Undefined:
                val = Undefined(key)
            return val
        raise


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
        node.args = [self.visit(x, *args, **kwargs) for x in node.args]
        if node.star_args:
            node.star_args = self.visit(node.star_args, *args, **kwargs)
        if node.dstar_args:
            node.dstar_args = self.visit(node.dstar_args, *args, **kwargs)
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
        node.subs = [self.visit(x, *args, **kwargs) for x in node.subs]
        return node

    # Operators

    def _visitBoolOp(self, node, *args, **kwargs):
        node.nodes = [self.visit(x, *args, **kwargs) for x in node.nodes]
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
        node.ops = [(op, self.visit(n, *args, **kwargs)) for op, n in  node.ops]
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

    def visitDict(self, node, *args, **kwargs):
        node.items = [(self.visit(k, *args, **kwargs),
                       self.visit(v, *args, **kwargs)) for k, v in node.items]
        return node

    def visitGenExpr(self, node, *args, **kwargs):
        node.code = self.visit(node.code, *args, **kwargs)
        node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def visitGenExprFor(self, node, *args, **kwargs):
        node.assign = self.visit(node.assign, *args, **kwargs)
        node.iter = self.visit(node.iter, *args, **kwargs)
        node.ifs = [self.visit(x, *args, **kwargs) for x in node.ifs]
        return node

    def visitGenExprIf(self, node, *args, **kwargs):
        node.test = self.visit(node.test, *args, **kwargs)
        return node

    def visitGenExprInner(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        node.quals = [self.visit(x, *args, **kwargs) for x in node.quals]
        return node

    def visitKeyword(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        return node

    def visitList(self, node, *args, **kwargs):
        node.nodes = [self.visit(n, *args, **kwargs) for n in node.nodes]
        return node

    def visitListComp(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, *args, **kwargs)
        node.quals = [self.visit(x, *args, **kwargs) for x in node.quals]
        return node

    def visitListCompFor(self, node, *args, **kwargs):
        node.assign = self.visit(node.assign, *args, **kwargs)
        node.list = self.visit(node.list, *args, **kwargs)
        node.ifs = [self.visit(x, *args, **kwargs) for x in node.ifs]
        return node

    def visitListCompIf(self, node, *args, **kwargs):
        node.test = self.visit(node.test, *args, **kwargs)
        return node

    def visitSlice(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, locals_=True, *args, **kwargs)
        if node.lower is not None:
            node.lower = self.visit(node.lower, *args, **kwargs)
        if node.upper is not None:
            node.upper = self.visit(node.upper, *args, **kwargs)
        return node

    def visitSliceobj(self, node, *args, **kwargs):
        node.nodes = [self.visit(x, *args, **kwargs) for x in node.nodes]
        return node

    def visitTuple(self, node, *args, **kwargs):
        node.nodes = [self.visit(n, *args, **kwargs) for n in node.nodes]
        return node


class ExpressionASTTransformer(ASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for template expressions.
    """

    def visitConst(self, node, locals_=False):
        if isinstance(node.value, str):
            return ast.Const(node.value.decode('utf-8'))
        return node

    def visitGenExprIf(self, node, *args, **kwargs):
        node.test = self.visit(node.test, locals_=True)
        return node

    def visitGenExprInner(self, node, *args, **kwargs):
        node.expr = self.visit(node.expr, locals_=True)
        node.quals = [self.visit(x) for x in node.quals]
        return node

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
        node.quals = [self.visit(qual, locals_=True) for qual in node.quals]
        return node

    def visitName(self, node, locals_=False):
        func_args = [ast.Name('data'), ast.Const(node.name)]
        if locals_:
            func_args.append(ast.CallFunc(ast.Name('locals'), []))
        return ast.CallFunc(ast.Name('_lookup_name'), func_args)

    def visitSubscript(self, node, locals_=False):
        return ast.CallFunc(ast.Name('_lookup_item'), [
            ast.Name('data'), self.visit(node.expr, locals_=locals_),
            ast.Tuple([self.visit(sub, locals_=locals_) for sub in node.subs])
        ])
