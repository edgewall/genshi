# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many individuals.
# For the exact contribution history, see the revision history and logs,
# available at http://genshi.edgewall.org/log/.

"""Support for "safe" evaluation of Python expressions."""

__all__ = ['ast', 'parse', 'ASTTransformer', 'TemplateASTTransformer', 'ExpressionASTTransformer', 'BUILTINS', 'CONSTANTS', 'ExpressionCodeGenerator', 'ModuleCodeGenerator', 'wrap_tree']
__docformat__ = 'restructuredtext en'

import __builtin__
import _ast
ast = _ast
def parse(src, type):
    return compile(src, '', type, _ast.PyCF_ONLY_AST)

#from compiler.pycodegen import ExpressionCodeGenerator, ModuleCodeGenerator
from astcompiler import ExpressionCodeGenerator, ModuleCodeGenerator
import new
from textwrap import dedent

from genshi.core import Markup
from genshi.template.base import TemplateRuntimeError
from genshi.template.eval import Undefined
from genshi.util import flatten


BUILTINS = __builtin__.__dict__.copy()
BUILTINS.update({'Markup': Markup, 'Undefined': Undefined})
CONSTANTS = frozenset(['False', 'True', 'None', 'NotImplemented', 'Ellipsis'])

def _new(class_, *args, **kwargs):
    ret = class_()
    for attr, value in zip(ret._fields, args):
        if attr in kwargs:
            raise ValueError, "Field set both in args and kwargs"
        setattr(ret, attr, value)
    for attr, value in kwargs:
        setattr(ret, attr, value)
    return ret

class ASTTransformer(object):
    """General purpose base class for AST transformations.
    
    Every visitor method can be overridden to return an AST node that has been
    altered or replaced in some way.
    """

    def visit(self, node):
        #print "In", node
        if node is None:
            return None
        if type(node) is tuple:
            return tuple([self.visit(n) for n in node])
        visitor = getattr(self, 'visit%s' % node.__class__.__name__,
                          self._visitDefault)
        xxx = visitor(node)
        #print "Out", xxx
        return xxx
        #return visitor(node)

    def _clonerVisit(self, node):
        #print "Cloning", node.__class__
        clone = node.__class__()
        for name in getattr(clone, '_attributes', ()):
            try:
                setattr(clone, 'name', getattr(node, name))
            except AttributeError:
                pass
        for name in clone._fields:
            try:
                value = getattr(node, name)
                #print value
            except AttributeError:
                pass
            else:
                #print "Jawohl", value,
                if value is None:
                    pass
                elif isinstance(value, list):
                    value = [self.visit(x) for x in value]
                elif isinstance(value, tuple):
                    value = tuple(self.visit(x) for x in value)
                else: 
                    value = self.visit(value)
                #print value
                setattr(clone, name, value)
        #if isinstance(node, (ast.Class, ast.Function, ast.Lambda,
        #                     ast.GenExpr)):
        #    node.filename = '<string>' # workaround for bug in pycodegen
        #print "Returning", clone
        return clone

    visitModule = _clonerVisit
    visitInteractive = _clonerVisit
    visitExpression = _clonerVisit
    visitSuite = _clonerVisit


    visitFunctionDef = _clonerVisit
    visitClassDef = _clonerVisit
    visitReturn = _clonerVisit
    visitDelete = _clonerVisit
    visitAssign = _clonerVisit
    visitAugAssign = _clonerVisit
    visitPrint = _clonerVisit
    visitFor = _clonerVisit
    visitWhile = _clonerVisit
    visitIf = _clonerVisit
    visitWith = _clonerVisit
    visitRaise = _clonerVisit
    visitTryExcept = _clonerVisit
    visitTryFinally = _clonerVisit
    visitAssert = _clonerVisit

    visitImport = _clonerVisit
    visitImportFrom = _clonerVisit
    visitExec = _clonerVisit
    visitGlobal = _clonerVisit
    visitExpr = _clonerVisit
    # Pass, Break, Continue don't need to be copied


    visitBoolOp = _clonerVisit
    visitBinOp = _clonerVisit
    visitUnaryOp = _clonerVisit
    visitLambda = _clonerVisit
    visitIfExp = _clonerVisit
    visitDict = _clonerVisit
    visitListComp = _clonerVisit
    visitGeneratorExp = _clonerVisit
    visitYield = _clonerVisit
    visitCompare = _clonerVisit
    visitCall = _clonerVisit
    visitRepr = _clonerVisit
    # Num, Str don't need to be copied


    visitAttribute = _clonerVisit
    visitSubscript = _clonerVisit
    visitName = _clonerVisit
    visitList = _clonerVisit
    visitTuple = _clonerVisit

    visitcomprehension = _clonerVisit
    visitexcepthandler = _clonerVisit
    visitarguments = _clonerVisit
    visitkeyword = _clonerVisit
    visitalias = _clonerVisit

    visitSlice = _clonerVisit
    visitExtSlice = _clonerVisit
    visitIndex = _clonerVisit

    del _clonerVisit

    def _visitDefault(self, node):
        return node

class TemplateASTTransformer(ASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.
    """

    def __init__(self):
        self.locals = [CONSTANTS]

    def _extract_names(self, node):
        arguments = set()
        def _process(node):
            if isinstance(node, _ast.Name):
                arguments.add(node.id)
            elif isinstance(node, _ast.Tuple):
                for elt in node.elts:
                    _process(node)
        for arg in node.args:
            _process(arg)
        if getattr(node, 'varargs', None):
            arguments.add(node.args.varargs)
        if getattr(node, 'kwargs', None):
            arguments.add(node.args.kwargs)
        return arguments

    def visitStr(self, node):
        if isinstance(node.s, str):
            try: # If the string is ASCII, return a `str` object
                node.s.decode('ascii')
            except ValueError: # Otherwise return a `unicode` object
                return _new(_ast.Str, node.s.decode('utf-8'))
        return node

    #def visitAssign(self, node):
    #    if len(self.locals) > 1:
    #        self.locals[-1].update(name.id for name in node.targets)
    #    return ASTTransformer.visitAssign(self, node)

    #def visitAugAssign(self, node):
    #    if len(self.locals) > 1:
    #        self.locals[-1].add(node.target.id)
    #    return ASTTransformer.visitAugAssign(self, node)
    #    if isinstance(node.target, ast.Name) \
    #            and node.target.id not in flatten(self.locals):
    #        name = node.target.id
    #        #TODO
    #        node.target = ast.Subscript(ast.Name('__data__'), 'OP_APPLY',
    #                                  [ast.Str(name)])
    #        node.expr = self.visit(node.expr)
    #        return ast.If([
    #            (ast.Compare(ast.Const(name), [('in', ast.Name('__data__'))]),
    #             ast.Stmt([node]))],
    #            ast.Stmt([ast.Raise(ast.CallFunc(ast.Name('UndefinedError'),
    #                                             [ast.Const(name)]),
    #                                None, None)]))
    #    else:
    #        return ASTTransformer.visitAugAssign(self, node)

    def visitClassDef(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
        self.locals.append(set())
        try:
            return ASTTransformer.visitClassDef(self, node)
        finally:
            self.locals.pop()

    def visitFor(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitFor(self, node)
        finally:
            self.locals.pop()

    def visitFunctionDef(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)

        self.locals.append(self._extract_names(node.args))
        try:
            return ASTTransformer.visitFunctionDef(self, node)
        finally:
            self.locals.pop()


    # GeneratorExp(expr elt, comprehension* generators)
    def visitGeneratorExp(self, node):
        gens = []
        # need to visit them in inverse order
        for generator in node.generators[::-1]:
            # comprehension = (expr target, expr iter, expr* ifs)
            self.locals.append(set())
            gen = _new(_ast.comprehension, self.visit(generator.target),
                            self.visit(generator.iter),
                            [self.visit(if_) for if_ in generator.ifs])
            gens.append(gen)
        gens.reverse()

        # use node.__class__ to make it reusable as ListComp
        ret = _new(node.__class__, self.visit(node.elt), gens)
        #delete inserted locals
        del self.locals[-len(node.generators):]
        return ret

    # ListComp(expr elt, comprehension* generators)
    visitListComp = visitGeneratorExp

    def visitLambda(self, node):
        self.locals.append(self._extract_names(node.args))
        try:
            return ASTTransformer.visitLambda(self, node)
        finally:
            self.locals.pop()

    def visitName(self, node):
        # If the name refers to a local inside a lambda, list comprehension, or
        # generator expression, leave it alone
        if isinstance(node.ctx, (_ast.Load, _ast.AugLoad,)) and \
                node.id not in flatten(self.locals):
            # Otherwise, translate the name ref into a context lookup
            name = _new(_ast.Name, '_lookup_name', _ast.Load())
            namearg = _new(_ast.Name, '__data__', _ast.Load())
            strarg = _new(_ast.Str, node.id)
            node = _new(_ast.Call, name, [namearg, strarg], [])
        elif isinstance(node.ctx, (_ast.Store, _ast.AugStore,)):
            if len(self.locals) > 1:
                self.locals[-1].add(node.id)

        return node


class ExpressionASTTransformer(TemplateASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.
    """

    def visitAttribute(self, node):
        if node.ctx != _ast.Load and node.ctx == _ast.AugLoad:
            return ASTTransformer.visitAttribute(self, node)

        func = _new(_ast.Name, '_lookup_attr', _ast.Load())
        args = [self.visit(node.value), _new(_ast.Str, node.attr)]
        call = _new(_ast.Call, func, args, [])
        return call

    def visitSubscript(self, node):
        if node.ctx != _ast.Load and node.ctx == _ast.AugLoad \
                or not isinstance(node.slice, _ast.Index):
            return ASTTransformer.visitSubscript(self, node)

        if isinstance(node.slice, _ast.Index):
            inds = (self.visit(node.slice.value),)
        if isinstance(node.slice, _ast.ExtSlice):
            inds = []
            for index in node.slice:
                if not isinstance(index, _ast.Index):
                    return ASTTransformer.visitSubscript(self, node)
                inds.append(self.visit(index.value))
            inds = tuple(inds)

        func = _new(_ast.Name, '_lookup_item', _ast.Load())
        args = [self.visit(node.value), _new(_ast.Tuple, inds, _ast.Load())]
        call = _new(_ast.Call, func, args, [])
        return call

def _assignment(ast):
    """Takes the AST representation of an assignment, and returns a function
    that applies the assignment of a given value to a dictionary.           
    """                                                                     
    def _names(node):                                                       
        if isinstance(node, _ast.Tuple):   
            # TODO
            return tuple([_names(child) for child in node.elts])
        elif isinstance(node, _ast.Name):   
            return node.id                                                
    def _assign(data, value, names=_names(ast)):                            
        if type(names) is tuple:                                            
            for idx in range(len(names)):                                   
                _assign(data, value[idx], names[idx])                       
        else:                                                               
            data[names] = value                                             
    return _assign    

def wrap_tree(source, mode):
    assert isinstance(source, ast.AST), \
        'Expected string or AST node, but got %r' % source
    if mode == 'eval':
        node = ast.Expression()
        node.body = source
    else:
        node = ast.Module()
        node.body = [source]
    return node
