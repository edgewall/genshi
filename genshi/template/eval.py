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

__all__ = ['Code', 'Expression', 'Suite', 'LenientLookup', 'StrictLookup',
           'Undefined', 'UndefinedError']
__docformat__ = 'restructuredtext en'


class Code(object):
    """Abstract base class for the `Expression` and `Suite` classes."""
    __slots__ = ['source', 'code', '_globals']

    def __init__(self, source, filename=None, lineno=-1, lookup='lenient'):
        """Create the code object, either from a string, or from an AST node.
        
        :param source: either a string containing the source code, or an AST
                       node
        :param filename: the (preferably absolute) name of the file containing
                         the code
        :param lineno: the number of the line on which the code was found
        :param lookup: the lookup class that defines how variables are looked
                       up in the context. Can be either `LenientLookup` (the
                       default), `StrictLookup`, or a custom lookup class
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
        if lookup is None:
            lookup = LenientLookup
        elif isinstance(lookup, basestring):
            lookup = {'lenient': LenientLookup, 'strict': StrictLookup}[lookup]
        self._globals = lookup.globals()

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
        _globals = self._globals
        _globals['data'] = data
        return eval(self.code, _globals, {'data': data})


class Suite(Code):
    """Executes Python statements used in templates.

    >>> data = dict(test='Foo', items=[1, 2, 3], dict={'some': 'thing'})
    >>> Suite("foo = dict['some']").execute(data)
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
        _globals = self._globals
        _globals['data'] = data
        exec self.code in _globals, data


UNDEFINED = object()


class UndefinedError(TemplateRuntimeError):
    """Exception thrown when a template expression attempts to access a variable
    not defined in the context.
    
    :see: `LenientLookup`, `StrictLookup`
    """
    def __init__(self, name, owner=UNDEFINED):
        if owner is not UNDEFINED:
            message = '%s has no member named "%s"' % (repr(owner), name)
        else:
            message = '"%s" not defined' % name
        TemplateRuntimeError.__init__(self, message)


class Undefined(object):
    """Represents a reference to an undefined variable.
    
    Unlike the Python runtime, template expressions can refer to an undefined
    variable without causing a `NameError` to be raised. The result will be an
    instance of the `Undefined` class, which is treated the same as ``False`` in
    conditions, but raise an exception on any other operation:
    
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
    UndefinedError: "foo" not defined

    >>> foo.bar
    Traceback (most recent call last):
        ...
    UndefinedError: "foo" not defined
    
    :see: `LenientLookup`
    """
    __slots__ = ['_name', '_owner']

    def __init__(self, name, owner=UNDEFINED):
        """Initialize the object.
        
        :param name: the name of the reference
        :param owner: the owning object, if the variable is accessed as a member
        """
        self._name = name
        self._owner = owner

    def __iter__(self):
        return iter([])

    def __nonzero__(self):
        return False

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self._name)

    def __str__(self):
        return 'undefined'

    def _die(self, *args, **kwargs):
        """Raise an `UndefinedError`."""
        __traceback_hide__ = True
        raise UndefinedError(self._name, self._owner)
    __call__ = __getattr__ = __getitem__ = _die


class LookupBase(object):
    """Abstract base class for variable lookup implementations."""

    def globals(cls):
        """Construct the globals dictionary to use as the execution context for
        the expression or suite.
        """
        return {
            '_lookup_name': cls.lookup_name,
            '_lookup_attr': cls.lookup_attr,
            '_lookup_item': cls.lookup_item
        }
    globals = classmethod(globals)

    def lookup_name(cls, data, name):
        __traceback_hide__ = True
        val = data.get(name, UNDEFINED)
        if val is UNDEFINED:
            val = BUILTINS.get(name, val)
            if val is UNDEFINED:
                return cls.undefined(name)
        return val
    lookup_name = classmethod(lookup_name)

    def lookup_attr(cls, data, obj, key):
        __traceback_hide__ = True
        if hasattr(obj, key):
            return getattr(obj, key)
        try:
            return obj[key]
        except (KeyError, TypeError):
            return cls.undefined(key, owner=obj)
    lookup_attr = classmethod(lookup_attr)

    def lookup_item(cls, data, obj, key):
        __traceback_hide__ = True
        if len(key) == 1:
            key = key[0]
        try:
            return obj[key]
        except (AttributeError, KeyError, IndexError, TypeError), e:
            if isinstance(key, basestring):
                val = getattr(obj, key, UNDEFINED)
                if val is UNDEFINED:
                    return cls.undefined(key, owner=obj)
                return val
            raise
    lookup_item = classmethod(lookup_item)

    def undefined(cls, key, owner=UNDEFINED):
        """Can be overridden by subclasses to specify behavior when undefined
        variables are accessed.
        
        :param key: the name of the variable
        :param owner: the owning object, if the variable is accessed as a member
        """
        raise NotImplementedError
    undefined = classmethod(undefined)


class LenientLookup(LookupBase):
    """Default variable lookup mechanism for expressions.
    
    When an undefined variable is referenced using this lookup style, the
    reference evaluates to an instance of the `Undefined` class:
    
    >>> expr = Expression('nothing', lookup='lenient')
    >>> undef = expr.evaluate({})
    >>> undef
    <Undefined 'nothing'>
    
    The same will happen when a non-existing attribute or item is accessed on
    an existing object:
    
    >>> expr = Expression('something.nil', lookup='lenient')
    >>> expr.evaluate({'something': dict()})
    <Undefined 'nil'>
    
    See the documentation of the `Undefined` class for details on the behavior
    of such objects.
    
    :see: `StrictLookup`
    """
    def undefined(cls, key, owner=UNDEFINED):
        """Return an ``Undefined`` object."""
        __traceback_hide__ = True
        return Undefined(key, owner=owner)
    undefined = classmethod(undefined)


class StrictLookup(LookupBase):
    """Strict variable lookup mechanism for expressions.
    
    Referencing an undefined variable using this lookup style will immediately
    raise an ``UndefinedError``:
    
    >>> expr = Expression('nothing', lookup='strict')
    >>> expr.evaluate({})
    Traceback (most recent call last):
        ...
    UndefinedError: "nothing" not defined
    
    The same happens when a non-existing attribute or item is accessed on an
    existing object:
    
    >>> expr = Expression('something.nil', lookup='strict')
    >>> expr.evaluate({'something': dict()})
    Traceback (most recent call last):
        ...
    UndefinedError: {} has no member named "nil"
    """
    def undefined(cls, key, owner=UNDEFINED):
        """Raise an ``UndefinedError`` immediately."""
        __traceback_hide__ = True
        raise UndefinedError(key, owner=owner)
    undefined = classmethod(undefined)


def _parse(source, mode='eval'):
    if isinstance(source, unicode):
        source = '\xef\xbb\xbf' + source.encode('utf-8')
    return parse(source, mode)

def _compile(node, source=None, mode='eval', filename=None, lineno=-1):
    xform = {'eval': ExpressionASTTransformer}.get(mode, TemplateASTTransformer)
    tree = xform().visit(node)
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
BUILTINS.update({'Markup': Markup, 'Undefined': Undefined})


class ASTTransformer(object):
    """General purpose base class for AST transformations.
    
    Every visitor method can be overridden to return an AST node that has been
    altered or replaced in some way.
    """

    def visit(self, node):
        if node is None:
            return None
        if type(node) is tuple:
            return tuple([self.visit(n) for n in node])
        visitor = getattr(self, 'visit%s' % node.__class__.__name__,
                          self._visitDefault)
        return visitor(node)

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

    def visitAssAttr(self, node):
        node.expr = self.visit(node.expr)
        return node

    def visitAugAssign(self, node):
        node.node = self.visit(node.node)
        node.expr = self.visit(node.expr)
        return node

    def visitDecorators(self, node):
        node.nodes = [self.visit(x) for x in node.nodes]
        return node

    def visitExec(self, node):
        node.expr = self.visit(node.expr)
        node.locals = self.visit(node.locals)
        node.globals = self.visit(node.globals)
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

    def visitReturn(self, node):
        node.value = self.visit(node.value)
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
    visitAssTuple = visitAssList = _visitBoolOp

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
        self.locals = []

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

    def visitAugAssign(self, node):
        if isinstance(node.node, ast.Name):
            name = node.node.name
            node.node = ast.Subscript(ast.Name('data'), 'OP_APPLY',
                                      [ast.Const(name)])
            node.expr = self.visit(node.expr)
            return ast.If([
                (ast.Compare(ast.Const(name), [('in', ast.Name('data'))]),
                 ast.Stmt([node]))],
                ast.Stmt([ast.Raise(ast.CallFunc(ast.Name('UndefinedError'),
                                                 [ast.Const(name)]),
                                    None, None)]))
        else:
            return ASTTransformer.visitAugAssign(self, node)

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


class ExpressionASTTransformer(TemplateASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.
    """

    def visitGetattr(self, node):
        return ast.CallFunc(ast.Name('_lookup_attr'), [
            ast.Name('data'), self.visit(node.expr),
            ast.Const(node.attrname)
        ])

    def visitSubscript(self, node):
        return ast.CallFunc(ast.Name('_lookup_item'), [
            ast.Name('data'), self.visit(node.expr),
            ast.Tuple([self.visit(sub) for sub in node.subs])
        ])
