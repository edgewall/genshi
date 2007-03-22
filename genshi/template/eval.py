# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
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
from compiler.pycodegen import ExpressionCodeGenerator, ModuleCodeGenerator
import new
try:
    set
except NameError:
    from sets import Set as set
import sys

from genshi.core import Markup
from genshi.template.base import TemplateRuntimeError
from genshi.util import flatten

__all__ = ['Expression', 'Suite']
__docformat__ = 'restructuredtext en'


class Code(object):
    """Abstract base class for the `Expression` and `Suite` classes."""
    __slots__ = ['source', 'code']

    def __init__(self, source, filename=None, lineno=-1):
        """Create the code object, either from a string, or from an AST node.
        
        :param source: either a string containing the source code, or an AST
                       node
        :param filename: the (preferably absolute) name of the file containing
                         the code
        :param lineno: the number of the line on which the code was found
        """
        if isinstance(source, basestring):
            self.source = source
            node = _parse(source, mode=self.mode)
        else:
            assert isinstance(source, ast.Node)
            self.source = '?'
            if self.mode == 'eval':
                node = ast.Expression(source)
            else:
                node = ast.Module(None, source)

        self.code = _compile(node, self.source, mode=self.mode,
                             filename=filename, lineno=lineno)

    def __eq__(self, other):
        return (type(other) == type(self)) and (self.code == other.code)

    def __hash__(self):
        return hash(self.code)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.source)


class Expression(Code):
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
    any object attribute:
    
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
    Built-in functions such as ``len()`` are also available in template
    expressions:
    
    >>> data = dict(items=[1, 2, 3])
    >>> Expression('len(items)').evaluate(data)
    3
    """
    __slots__ = []
    mode = 'eval'

    def evaluate(self, data):
        """Evaluate the expression against the given data dictionary.
        
        :param data: a mapping containing the data to evaluate against
        :return: the result of the evaluation
        """
        __traceback_hide__ = 'before_and_this'
        return eval(self.code, {'data': data,
                                '_lookup_name': _lookup_name,
                                '_lookup_attr': _lookup_attr,
                                '_lookup_item': _lookup_item,
                                'defined': _defined(data),
                                'value_of': _value_of(data)},
                               {'data': data})


class Suite(Code):
    """Executes Python statements used in templates.

    >>> data = dict(test='Foo', items=[1, 2, 3], dict={'some': 'thing'})
    >>> Suite('foo = dict.some').execute(data)
    >>> data['foo']
    'thing'
    """
    __slots__ = []
    mode = 'exec'

    def execute(self, data):
        """Execute the suite in the given data dictionary.
        
        :param data: a mapping containing the data to execute in
        """
        __traceback_hide__ = 'before_and_this'
        exec self.code in {'data': data,
                           '_lookup_name': _lookup_name,
                           '_lookup_attr': _lookup_attr,
                           '_lookup_item': _lookup_item,
                           'defined': _defined(data),
                           'value_of': _value_of(data)}, data


def _defined(data):
    def defined(name):
        """Return whether a variable with the specified name exists in the
        expression scope.
        """
        return name in data
    return defined

def _value_of(data):
    def value_of(name, default=None):
        """If a variable of the specified name is defined, return its value.
        Otherwise, return the provided default value, or ``None``.
        """
        return data.get(name, default)
    return value_of

def _parse(source, mode='eval'):
    if isinstance(source, unicode):
        source = '\xef\xbb\xbf' + source.encode('utf-8')
    return parse(source, mode)

def _compile(node, source=None, mode='eval', filename=None, lineno=-1):
    tree = TemplateASTTransformer().visit(node)
    if isinstance(filename, unicode):
        # unicode file names not allowed for code objects
        filename = filename.encode('utf-8', 'replace')
    elif not filename:
        filename = '<string>'
    tree.filename = filename
    if lineno <= 0:
        lineno = 1

    if mode == 'eval':
        gen = ExpressionCodeGenerator(tree)
        name = '<Expression %s>' % (repr(source or '?'))
    else:
        gen = ModuleCodeGenerator(tree)
        name = '<Suite>'
    gen.optimized = True
    code = gen.getCode()

    # We'd like to just set co_firstlineno, but it's readonly. So we need to
    # clone the code object while adjusting the line number
    return new.code(0, code.co_nlocals, code.co_stacksize,
                    code.co_flags | 0x0040, code.co_code, code.co_consts,
                    code.co_names, code.co_varnames, filename, name, lineno,
                    code.co_lnotab, (), ())

BUILTINS = __builtin__.__dict__.copy()
BUILTINS.update({'Markup': Markup})
UNDEFINED = object()


class UndefinedError(TemplateRuntimeError):
    """Exception thrown when a template expression attempts to access a variable
    not defined in the context.
    """
    def __init__(self, name, owner=UNDEFINED):
        if owner is not UNDEFINED:
            orepr = repr(owner)
            if len(orepr) > 60:
                orepr = orepr[:60] + '...'
            message = '%s (%s) has no member named "%s"' % (
                type(owner).__name__, orepr, name
            )
        else:
            message = '"%s" not defined' % name
        TemplateRuntimeError.__init__(self, message)


def _lookup_name(data, name):
    __traceback_hide__ = True
    val = data.get(name, UNDEFINED)
    if val is UNDEFINED:
        val = BUILTINS.get(name, val)
        if val is UNDEFINED:
            raise UndefinedError(name)
    return val

def _lookup_attr(data, obj, key):
    __traceback_hide__ = True
    if hasattr(obj, key):
        return getattr(obj, key)
    try:
        return obj[key]
    except (KeyError, TypeError):
        raise UndefinedError(key, owner=obj)

def _lookup_item(data, obj, key):
    __traceback_hide__ = True
    if len(key) == 1:
        key = key[0]
    try:
        return obj[key]
    except (AttributeError, KeyError, IndexError, TypeError), e:
        if isinstance(key, basestring):
            val = getattr(obj, key, UNDEFINED)
            if val is UNDEFINED:
                raise UndefinedError(key, owner=obj)
            return val
        raise


class ASTTransformer(object):
    """General purpose base class for AST transformations.
    
    Every visitor method can be overridden to return an AST node that has been
    altered or replaced in some way.
    """
    _visitors = {}

    def visit(self, node):
        if node is None:
            return None
        v = self._visitors.get(node.__class__)
        if not v:
            v = getattr(self.__class__, 'visit%s' % node.__class__.__name__,
                        self.__class__._visitDefault)
            self._visitors[node.__class__] = v
        return v(self, node)

    def _visitDefault(self, node):
        return node

    def visitExpression(self, node):
        node.node = self.visit(node.node)
        return node

    def visitModule(self, node):
        node.node = self.visit(node.node)
        return node

    def visitStmt(self, node):
        node.nodes = [self.visit(x) for x in node.nodes]
        return node

    # Classes, Functions & Accessors

    def visitCallFunc(self, node):
        node.node = self.visit(node.node)
        node.args = [self.visit(x) for x in node.args]
        if node.star_args:
            node.star_args = self.visit(node.star_args)
        if node.dstar_args:
            node.dstar_args = self.visit(node.dstar_args)
        return node

    def visitClass(self, node):
        node.bases = [self.visit(x) for x in node.bases]
        node.code = self.visit(node.code)
        node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def visitFunction(self, node):
        if hasattr(node, 'decorators'):
            node.decorators = self.visit(node.decorators)
        node.defaults = [self.visit(x) for x in node.defaults]
        node.code = self.visit(node.code)
        node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def visitGetattr(self, node):
        node.expr = self.visit(node.expr)
        return node

    def visitLambda(self, node):
        node.code = self.visit(node.code)
        node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def visitSubscript(self, node):
        node.expr = self.visit(node.expr)
        node.subs = [self.visit(x) for x in node.subs]
        return node

    # Statements

    def visitAssert(self, node):
        node.test = self.visit(node.test)
        node.fail = self.visit(node.fail)
        return node

    def visitAssign(self, node):
        node.nodes = [self.visit(x) for x in node.nodes]
        node.expr = self.visit(node.expr)
        return node

    def visitDecorators(self, node):
        node.nodes = [self.visit(x) for x in node.nodes]
        return node

    def visitFor(self, node):
        node.assign = self.visit(node.assign)
        node.list = self.visit(node.list)
        node.body = self.visit(node.body)
        node.else_ = self.visit(node.else_)
        return node

    def visitIf(self, node):
        node.tests = [self.visit(x) for x in node.tests]
        node.else_ = self.visit(node.else_)
        return node

    def _visitPrint(self, node):
        node.nodes = [self.visit(x) for x in node.nodes]
        node.dest = self.visit(node.dest)
        return node
    visitPrint = visitPrintnl = _visitPrint

    def visitRaise(self, node):
        node.expr1 = self.visit(node.expr1)
        node.expr2 = self.visit(node.expr2)
        node.expr3 = self.visit(node.expr3)
        return node

    def visitTryExcept(self, node):
        node.body = self.visit(node.body)
        node.handlers = self.visit(node.handlers)
        node.else_ = self.visit(node.else_)
        return node

    def visitTryFinally(self, node):
        node.body = self.visit(node.body)
        node.final = self.visit(node.final)
        return node

    def visitWhile(self, node):
        node.test = self.visit(node.test)
        node.body = self.visit(node.body)
        node.else_ = self.visit(node.else_)
        return node

    def visitWith(self, node):
        node.expr = self.visit(node.expr)
        node.vars = [self.visit(x) for x in node.vars]
        node.body = self.visit(node.body)
        return node

    def visitYield(self, node):
        node.value = self.visit(node.value)
        return node

    # Operators

    def _visitBoolOp(self, node):
        node.nodes = [self.visit(x) for x in node.nodes]
        return node
    visitAnd = visitOr = visitBitand = visitBitor = visitBitxor = _visitBoolOp
    visitAssTuple = _visitBoolOp

    def _visitBinOp(self, node):
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        return node
    visitAdd = visitSub = _visitBinOp
    visitDiv = visitFloorDiv = visitMod = visitMul = visitPower = _visitBinOp
    visitLeftShift = visitRightShift = _visitBinOp

    def visitCompare(self, node):
        node.expr = self.visit(node.expr)
        node.ops = [(op, self.visit(n)) for op, n in  node.ops]
        return node

    def _visitUnaryOp(self, node):
        node.expr = self.visit(node.expr)
        return node
    visitUnaryAdd = visitUnarySub = visitNot = visitInvert = _visitUnaryOp
    visitBackquote = visitDiscard = _visitUnaryOp

    def visitIfExp(self, node):
        node.test = self.visit(node.test)
        node.then = self.visit(node.then)
        node.else_ = self.visit(node.else_)
        return node

    # Identifiers, Literals and Comprehensions

    def visitDict(self, node):
        node.items = [(self.visit(k),
                       self.visit(v)) for k, v in node.items]
        return node

    def visitGenExpr(self, node):
        node.code = self.visit(node.code)
        node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def visitGenExprFor(self, node):
        node.assign = self.visit(node.assign)
        node.iter = self.visit(node.iter)
        node.ifs = [self.visit(x) for x in node.ifs]
        return node

    def visitGenExprIf(self, node):
        node.test = self.visit(node.test)
        return node

    def visitGenExprInner(self, node):
        node.quals = [self.visit(x) for x in node.quals]
        node.expr = self.visit(node.expr)
        return node

    def visitKeyword(self, node):
        node.expr = self.visit(node.expr)
        return node

    def visitList(self, node):
        node.nodes = [self.visit(n) for n in node.nodes]
        return node

    def visitListComp(self, node):
        node.quals = [self.visit(x) for x in node.quals]
        node.expr = self.visit(node.expr)
        return node

    def visitListCompFor(self, node):
        node.assign = self.visit(node.assign)
        node.list = self.visit(node.list)
        node.ifs = [self.visit(x) for x in node.ifs]
        return node

    def visitListCompIf(self, node):
        node.test = self.visit(node.test)
        return node

    def visitSlice(self, node):
        node.expr = self.visit(node.expr)
        if node.lower is not None:
            node.lower = self.visit(node.lower)
        if node.upper is not None:
            node.upper = self.visit(node.upper)
        return node

    def visitSliceobj(self, node):
        node.nodes = [self.visit(x) for x in node.nodes]
        return node

    def visitTuple(self, node):
        node.nodes = [self.visit(n) for n in node.nodes]
        return node


class TemplateASTTransformer(ASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.
    """

    def __init__(self):
        self.locals = [set(['defined', 'value_of'])]

    def visitConst(self, node):
        if isinstance(node.value, str):
            try: # If the string is ASCII, return a `str` object
                node.value.decode('ascii')
            except ValueError: # Otherwise return a `unicode` object
                return ast.Const(node.value.decode('utf-8'))
        return node

    def visitAssName(self, node):
        if self.locals:
            self.locals[-1].add(node.name)
        return node

    def visitClass(self, node):
        self.locals.append(set())
        node = ASTTransformer.visitClass(self, node)
        self.locals.pop()
        return node

    def visitFor(self, node):
        self.locals.append(set())
        node = ASTTransformer.visitFor(self, node)
        self.locals.pop()
        return node

    def visitFunction(self, node):
        self.locals.append(set(node.argnames))
        node = ASTTransformer.visitFunction(self, node)
        self.locals.pop()
        return node

    def visitGenExpr(self, node):
        self.locals.append(set())
        node = ASTTransformer.visitGenExpr(self, node)
        self.locals.pop()
        return node

    def visitGetattr(self, node):
        return ast.CallFunc(ast.Name('_lookup_attr'), [
            ast.Name('data'), self.visit(node.expr),
            ast.Const(node.attrname)
        ])

    def visitLambda(self, node):
        self.locals.append(set(flatten(node.argnames)))
        node = ASTTransformer.visitLambda(self, node)
        self.locals.pop()
        return node

    def visitListComp(self, node):
        self.locals.append(set())
        node = ASTTransformer.visitListComp(self, node)
        self.locals.pop()
        return node

    def visitName(self, node):
        # If the name refers to a local inside a lambda, list comprehension, or
        # generator expression, leave it alone
        for frame in self.locals:
            if node.name in frame:
                return node
        # Otherwise, translate the name ref into a context lookup
        func_args = [ast.Name('data'), ast.Const(node.name)]
        return ast.CallFunc(ast.Name('_lookup_name'), func_args)

    def visitSubscript(self, node):
        return ast.CallFunc(ast.Name('_lookup_item'), [
            ast.Name('data'), self.visit(node.expr),
            ast.Tuple([self.visit(sub) for sub in node.subs])
        ])
