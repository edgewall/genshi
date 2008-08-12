# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 Edgewall Software
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
from textwrap import dedent

from genshi.core import Markup
from genshi.template.base import TemplateRuntimeError
from genshi.template.eval import Undefined
from genshi.util import flatten

__all__ = ['ast', 'parse', 'ASTTransformer', 'TemplateASTTransformer', 'ExpressionASTTransformer', 'BUILTINS', 'CONSTANTS', 'ExpressionCodeGenerator', 'ModuleCodeGenerator', 'wrap_tree']  
__docformat__ = 'restructuredtext en'

BUILTINS = __builtin__.__dict__.copy()
BUILTINS.update({'Markup': Markup, 'Undefined': Undefined})
CONSTANTS = frozenset(['False', 'True', 'None', 'NotImplemented', 'Ellipsis'])

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

    def _clone(self, node, *args):
        lineno = getattr(node, 'lineno', None)
        node = node.__class__(*args)
        if lineno is not None:
            node.lineno = lineno
        if isinstance(node, (ast.Class, ast.Function, ast.Lambda,
                             ast.GenExpr)):
            node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def _visitDefault(self, node):
        return node

    def visitExpression(self, node):
        return self._clone(node, self.visit(node.node))

    def visitModule(self, node):
        return self._clone(node, node.doc, self.visit(node.node))

    def visitStmt(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    # Classes, Functions & Accessors

    def visitCallFunc(self, node):
        return self._clone(node, self.visit(node.node),
            [self.visit(x) for x in node.args],
            node.star_args and self.visit(node.star_args) or None,
            node.dstar_args and self.visit(node.dstar_args) or None
        )

    def visitClass(self, node):
        return self._clone(node, node.name, [self.visit(x) for x in node.bases],
            node.doc, self.visit(node.code)
        )

    def visitFrom(self, node):
        if not has_star_import_bug or node.names != [('*', None)]:
            # This is a Python 2.4 bug. Only if we have a broken Python
            # version we have to apply the hack
            return node
        return ast.Discard(ast.CallFunc(
            ast.Name('_star_import_patch'),
            [ast.Name('__data__'), ast.Const(node.modname)], None, None
        ), lineno=node.lineno)

    def visitFunction(self, node):
        args = []
        if hasattr(node, 'decorators'):
            args.append(self.visit(node.decorators))
        return self._clone(node, *args + [
            node.name,
            node.argnames,
            [self.visit(x) for x in node.defaults],
            node.flags,
            node.doc,
            self.visit(node.code)
        ])

    def visitGetattr(self, node):
        return self._clone(node, self.visit(node.expr), node.attrname)

    def visitLambda(self, node):
        node = self._clone(node, node.argnames,
            [self.visit(x) for x in node.defaults], node.flags,
            self.visit(node.code)
        )
        return node

    def visitSubscript(self, node):
        return self._clone(node, self.visit(node.expr), node.flags,
            [self.visit(x) for x in node.subs]
        )

    # Statements

    def visitAssert(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.fail))

    def visitAssign(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes],
            self.visit(node.expr)
        )

    def visitAssAttr(self, node):
        return self._clone(node, self.visit(node.expr), node.attrname,
            node.flags
        )

    def visitAugAssign(self, node):
        return self._clone(node, self.visit(node.node), node.op,
            self.visit(node.expr)
        )

    def visitDecorators(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    def visitExec(self, node):
        return self._clone(node, self.visit(node.expr), self.visit(node.locals),
            self.visit(node.globals)
        )

    def visitFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.list),
            self.visit(node.body), self.visit(node.else_)
        )

    def visitIf(self, node):
        return self._clone(node, [self.visit(x) for x in node.tests],
            self.visit(node.else_)
        )

    def _visitPrint(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes],
            self.visit(node.dest)
        )
    visitPrint = visitPrintnl = _visitPrint

    def visitRaise(self, node):
        return self._clone(node, self.visit(node.expr1), self.visit(node.expr2),
            self.visit(node.expr3)
        )

    def visitReturn(self, node):
        return self._clone(node, self.visit(node.value))

    def visitTryExcept(self, node):
        return self._clone(node, self.visit(node.body), self.visit(node.handlers),
            self.visit(node.else_)
        )

    def visitTryFinally(self, node):
        return self._clone(node, self.visit(node.body), self.visit(node.final))

    def visitWhile(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.body),
            self.visit(node.else_)
        )

    def visitWith(self, node):
        return self._clone(node, self.visit(node.expr),
            [self.visit(x) for x in node.vars], self.visit(node.body)
        )

    def visitYield(self, node):
        return self._clone(node, self.visit(node.value))

    # Operators

    def _visitBoolOp(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])
    visitAnd = visitOr = visitBitand = visitBitor = visitBitxor = _visitBoolOp
    visitAssTuple = visitAssList = _visitBoolOp

    def _visitBinOp(self, node):
        return self._clone(node,
            (self.visit(node.left), self.visit(node.right))
        )
    visitAdd = visitSub = _visitBinOp
    visitDiv = visitFloorDiv = visitMod = visitMul = visitPower = _visitBinOp
    visitLeftShift = visitRightShift = _visitBinOp

    def visitCompare(self, node):
        return self._clone(node, self.visit(node.expr),
            [(op, self.visit(n)) for op, n in  node.ops]
        )

    def _visitUnaryOp(self, node):
        return self._clone(node, self.visit(node.expr))
    visitUnaryAdd = visitUnarySub = visitNot = visitInvert = _visitUnaryOp
    visitBackquote = visitDiscard = _visitUnaryOp

    def visitIfExp(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.then),
            self.visit(node.else_)
        )

    # Identifiers, Literals and Comprehensions

    def visitDict(self, node):
        return self._clone(node, 
            [(self.visit(k), self.visit(v)) for k, v in node.items]
        )

    def visitGenExpr(self, node):
        return self._clone(node, self.visit(node.code))

    def visitGenExprFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.iter),
            [self.visit(x) for x in node.ifs]
        )

    def visitGenExprIf(self, node):
        return self._clone(node, self.visit(node.test))

    def visitGenExprInner(self, node):
        quals = [self.visit(x) for x in node.quals]
        return self._clone(node, self.visit(node.expr), quals)

    def visitKeyword(self, node):
        return self._clone(node, node.name, self.visit(node.expr))

    def visitList(self, node):
        return self._clone(node, [self.visit(n) for n in node.nodes])

    def visitListComp(self, node):
        quals = [self.visit(x) for x in node.quals]
        return self._clone(node, self.visit(node.expr), quals)

    def visitListCompFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.list),
            [self.visit(x) for x in node.ifs]
        )

    def visitListCompIf(self, node):
        return self._clone(node, self.visit(node.test))

    def visitSlice(self, node):
        return self._clone(node, self.visit(node.expr), node.flags,
            node.lower and self.visit(node.lower) or None,
            node.upper and self.visit(node.upper) or None
        )

    def visitSliceobj(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    def visitTuple(self, node):
        return self._clone(node, [self.visit(n) for n in node.nodes])


class TemplateASTTransformer(ASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.
    """

    def __init__(self):
        self.locals = [CONSTANTS]

    def visitConst(self, node):
        if isinstance(node.value, str):
            try: # If the string is ASCII, return a `str` object
                node.value.decode('ascii')
            except ValueError: # Otherwise return a `unicode` object
                return ast.Const(node.value.decode('utf-8'))
        return node

    def visitAssName(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
        return node

    def visitAugAssign(self, node):
        if isinstance(node.node, ast.Name) \
                and node.node.name not in flatten(self.locals):
            name = node.node.name
            node.node = ast.Subscript(ast.Name('__data__'), 'OP_APPLY',
                                      [ast.Const(name)])
            node.expr = self.visit(node.expr)
            return ast.If([
                (ast.Compare(ast.Const(name), [('in', ast.Name('__data__'))]),
                 ast.Stmt([node]))],
                ast.Stmt([ast.Raise(ast.CallFunc(ast.Name('UndefinedError'),
                                                 [ast.Const(name)]),
                                    None, None)]))
        else:
            return ASTTransformer.visitAugAssign(self, node)

    def visitClass(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
        self.locals.append(set())
        try:
            return ASTTransformer.visitClass(self, node)
        finally:
            self.locals.pop()

    def visitFor(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitFor(self, node)
        finally:
            self.locals.pop()

    def visitFunction(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
        self.locals.append(set(node.argnames))
        try:
            return ASTTransformer.visitFunction(self, node)
        finally:
            self.locals.pop()

    def visitGenExpr(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitGenExpr(self, node)
        finally:
            self.locals.pop()

    def visitLambda(self, node):
        self.locals.append(set(flatten(node.argnames)))
        try:
            return ASTTransformer.visitLambda(self, node)
        finally:
            self.locals.pop()

    def visitListComp(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitListComp(self, node)
        finally:
            self.locals.pop()

    def visitName(self, node):
        # If the name refers to a local inside a lambda, list comprehension, or
        # generator expression, leave it alone
        if node.name not in flatten(self.locals):
            # Otherwise, translate the name ref into a context lookup
            func_args = [ast.Name('__data__'), ast.Const(node.name)]
            node = ast.CallFunc(ast.Name('_lookup_name'), func_args)
        return node


class ExpressionASTTransformer(TemplateASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.
    """

    def visitGetattr(self, node):
        return ast.CallFunc(ast.Name('_lookup_attr'), [
            self.visit(node.expr),
            ast.Const(node.attrname)
        ])

    def visitSubscript(self, node):
        return ast.CallFunc(ast.Name('_lookup_item'), [
            self.visit(node.expr),
            ast.Tuple([self.visit(sub) for sub in node.subs])
        ])

def wrap_tree(source, mode):
    assert isinstance(source, ast.Node), \
        'Expected string or AST node, but got %r' % source
    if mode == 'eval':
        node = ast.Expression(source)
    else:
        node = ast.Module(None, source)
