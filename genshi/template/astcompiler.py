# -*- coding: utf-8 -*-
#
# Copyright (C) 2008 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Module generating Python code from AST tree and then compiling it"""

try:
    import _ast
except ImportError:
    from genshi.template.ast24 import _ast

__docformat__ = 'restructuredtext en'


class CodeGenerator(object):
    """General purpose base class for AST transformations.

    Every visitor method can be overridden to return an AST node that has been
    altered or replaced in some way.
    """
    def __init__(self, tree):
        self.lines_info = []
        self.line_info = None
        self.code = ""
        self.line = None
        self.last = None
        self.indent = 0
        self.blame_stack = []
        self.visit(tree)
        if self.line.strip() != "":
            self.code += self.line + "\n"
            self.lines_info.append(self.line_info)
        self.line = None
        self.line_info = None

    def get_code(self):
        return compile(self.code, '', self.type)

    def new_line(self):
        if self.line is not None:
            self.code += self.line + '\n'
            self.lines_info.append(self.line_info)
        self.line = ' '*4*self.indent
        if len(self.blame_stack) == 0:
            self.line_info = []
            self.last = None
        else:
            self.line_info = [(0, self.blame_stack[-1],)]
            self.last = self.blame_stack[-1]

    def write(self, s):
        if len(s) == 0:
            return
        if len(self.blame_stack) == 0:
            if self.last is not None:
                self.last = None
                self.line_info.append((len(self.line), self.last))
        else:
            if self.last != self.blame_stack[-1]:
                self.last = self.blame_stack[-1]
                self.line_info.append((len(self.line), self.last))
        self.line += s

    def change_indent(self, delta):
        self.indent += delta

    def visit(self, node):
        #print "In", node
        if node is None:
            return None
        if type(node) is tuple:
            return tuple([self.visit(n) for n in node])
        try:
            self.blame_stack.append((node.lineno, node.col_offset,))
            info = True
        except AttributeError:
            info = False
        visitor = getattr(self, 'visit%s' % node.__class__.__name__,
                          self._visitDefault)
        ret = visitor(node)
        if info:
            self.blame_stack.pop()
        return ret
        #print "Out", node

    def _visitDefault(self, node):
        raise Exception('Unhandled node type %r with object %r' % (type(node), repr(node)))
    def visitModule(self, node):
        for n in node.body:
            self.visit(n)
    visitInteractive = visitModule
    visitSuite = visitModule

    def visitExpression(self, node):
        self.new_line()
        return self.visit(node.body)

    # arguments = (expr* args, identifier? vararg,
    #                 identifier? kwarg, expr* defaults)
    def visitarguments(self, node):
        first = True
        for i, arg in enumerate(node.args):
            if not first:
                self.write(', ')
            else:
                first = False
            self.visit(arg)
            if i < len(node.defaults):
                self.write('=')
                self.visit(node.defaults[i])
        if getattr(node, 'vararg', None):
            if not first:
                self.write(', ')
            else:
                first = False
            self.write('*' + node.vararg)
        if getattr(node, 'kwarg', None):
            if not first:
                self.write(', ')
            else:
                first = False
            self.write('**' + node.kwarg)

    # FunctionDef(identifier name, arguments args,
    #                           stmt* body, expr* decorators)
    def visitFunctionDef(self, node):
        for decorator in getattr(node, 'decorators', ()):
            self.new_line()
            self.write('@')
            self.visit(decorator)
        self.new_line()
        self.write("def %s("%node.name)
        self.visit(node.args)
        self.write("):")
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)


    # ClassDef(identifier name, expr* bases, stmt* body)
    def visitClassDef(self, node):
        self.new_line()
        self.write("class %s"%node.name)
        if node.bases:
            self.write('(')
            self.visit(node.bases[0])
            for base in node.bases[1:]:
                self.write(', ')
                self.visit(base)
            self.write(')')
        self.write(':')
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)
    # Return(expr? value)
    def visitReturn(self, node):
        self.new_line()
        self.write("return")
        if getattr(node, 'value', None):
            self.write(" ")
            self.visit(node.value)
    # Delete(expr* targets)
    def visitDelete(self, node):
        self.new_line()
        self.write("del ")
        self.visit(node.targets[0])
        for target in node.targets[1:]:
            self.write(", ")
            self.visit(target)

    # Assign(expr* targets, expr value)
    def visitAssign(self, node):
        self.new_line()
        for target in node.targets:
            self.visit(target)
            self.write(' = ')
        self.visit(node.value)

    # AugAssign(expr target, operator op, expr value)
    def visitAugAssign(self, node):
        self.new_line()
        self.visit(node.target)
        self.write(" %s= "%self.binary_operators[node.op.__class__])
        self.visit(node.value)

    # Print(expr? dest, expr* values, bool nl)
    def visitPrint(self, node):
        self.new_line()
        self.write("print")
        if getattr(node, 'dest', None):
            self.write(" >> ")
            self.visit(node.dest)
            if getattr(node, 'values', None):
                self.write(", ")
        if getattr(node, 'values', None):
            self.visit(node.values[0])
            for value in node.values[1:]:
                self.write(", ")
                self.visit(value)
        if not node.nl:
            self.write(",")

    # For(expr target, expr iter, stmt* body, stmt* orelse)
    def visitFor(self, node):
        self.new_line()
        self.write("for ")
        self.visit(node.target)
        self.write(" in ")
        self.visit(node.iter)
        self.write(":")
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)
        if getattr(node, 'orelse', None):
            self.new_line()
            self.write("else:")
            self.change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self.change_indent(-1)

    # While(expr test, stmt* body, stmt* orelse)
    def visitWhile(self, node):
        self.new_line()
        self.write("while ")
        self.visit(node.test)
        self.write(":")
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)
        if getattr(node, 'orelse', None):
            self.new_line()
            self.write("else:")
            self.change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self.change_indent(-1)

    # If(expr test, stmt* body, stmt* orelse)
    def visitIf(self, node):
        self.new_line()
        self.write("if ")
        self.visit(node.test)
        self.write(":")
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)
        if getattr(node, 'orelse', None):
            self.new_line()
            self.write("else:")
            self.change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self.change_indent(-1)

    # With(expr context_expr, expr? optional_vars, stmt* body)
    def visitWith(self, node):
        self.new_line()
        self.write("with ")
        self.visit(node.context_expr)
        if getattr(node, "optional_vars", None):
            self.write(" as ")
            self.visit(node.optional_vars)
        self.write(":")
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)


    # Raise(expr? type, expr? inst, expr? tback)
    def visitRaise(self, node):
        self.new_line()
        self.write("raise")
        if not node.type:
            return
        self.write(" ")
        self.visit(node.type)
        if not node.inst:
            return
        self.write(", ")
        self.visit(node.inst)
        if not node.tback:
            return
        self.write(", ")
        self.visit(node.tback)

    # TryExcept(stmt* body, excepthandler* handlers, stmt* orelse)
    def visitTryExcept(self, node):
        self.new_line()
        self.write("try:")
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)
        if getattr(node, 'handlers', None):
            for handler in node.handlers:
                self.visit(handler)
        self.new_line()
        if getattr(node, 'orelse', None):
            self.write("else:")
            self.change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self.change_indent(-1)

    # excepthandler = (expr? type, expr? name, stmt* body)
    def visitExceptHandler(self, node):
        self.new_line()
        self.write("except")
        if getattr(node, 'type', None):
            self.write(' ')
            self.visit(node.type)
        if getattr(node, 'name', None):
            self.write(', ')
            self.visit(node.name)
        self.write(":")
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)
    visitexcepthandler = visitExceptHandler

    # TryFinally(stmt* body, stmt* finalbody)
    def visitTryFinally(self, node):
        self.new_line()
        self.write("try:")
        self.change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self.change_indent(-1)

        if getattr(node, 'finalbody', None):
            self.new_line()
            self.write("finally:")
            self.change_indent(1)
            for statement in node.finalbody:
                self.visit(statement)
            self.change_indent(-1)

    # Assert(expr test, expr? msg)
    def visitAssert(self, node):
        self.new_line()
        self.write("assert ")
        self.visit(node.test)
        if getattr(node, 'msg', None):
            self.write(", ")
            self.visit(node.msg)

    def visitalias(self, node):
        self.write(node.name)
        if getattr(node, 'asname', None):
            self.write(" as ")
            self.write(node.asname)

    # Import(alias* names)
    def visitImport(self, node):
        self.new_line()
        self.write("import ")
        self.visit(node.names[0])
        for name in node.names[1:]:
            self.write(", ")
            self.visit(name)

    # ImportFrom(identifier module, alias* names, int? level)
    def visitImportFrom(self, node):
        self.new_line()
        self.write("from ")
        if node.level:
            self.write("." * node.level)
        self.write(node.module)
        self.write(" import ")
        self.visit(node.names[0])
        for name in node.names[1:]:
            self.write(", ")
            self.visit(name)

    # Exec(expr body, expr? globals, expr? locals)
    def visitExec(self, node):
        self.new_line()
        self.write("exec ")
        self.visit(node.body)
        if not node.globals:
            return
        self.write(", ")
        self.visit(node.globals)
        if not node.locals:
            return
        self.write(", ")
        self.visit(node.locals)

    # Global(identifier* names)
    def visitGlobal(self, node):
        self.new_line()
        self.write("global ")
        self.visit(node.names[0])
        for name in node.names[1:]:
            self.write(", ")
            self.visit(name)

    # Expr(expr value)
    def visitExpr(self, node):
        self.new_line()
        self.visit(node.value)

    # Pass
    def visitPass(self, node):
        self.new_line()
        self.write("pass")

    # Break
    def visitBreak(self, node):
        self.new_line()
        self.write("break")

    # Continue
    def visitContinue(self, node):
        self.new_line()
        self.write("continue")


    ### EXPRESSIONS
    def add_parenthesis(f):
        def _f(self, node):
            self.write('(')
            f(self, node)
            self.write(')')
        return _f

    bool_operators = {_ast.And:'and', _ast.Or:'or'}
    # BoolOp(boolop op, expr* values)
    @add_parenthesis
    def visitBoolOp(self, node):
        joiner = " %s "%self.bool_operators[node.op.__class__]
        self.visit(node.values[0])
        for value in node.values[1:]:
            self.write(joiner)
            self.visit(value)

    binary_operators = {
        _ast.Add: '+',
        _ast.Sub: '-',
        _ast.Mult: '*',
        _ast.Div: '/',
        _ast.Mod: '%',
        _ast.Pow: '**',
        _ast.LShift: '<<',
        _ast.RShift: '>>',
        _ast.BitOr: '|',
        _ast.BitXor: '^',
        _ast.BitAnd: '&',
        _ast.FloorDiv: '//'
    }

    # BinOp(expr left, operator op, expr right)
    @add_parenthesis
    def visitBinOp(self, node):
        self.visit(node.left)
        self.write(" %s "%self.binary_operators[node.op.__class__])
        self.visit(node.right)

    unary_operators = {
        _ast.Invert: '~',
        _ast.Not: 'not',
        _ast.UAdd: '+',
        _ast.USub: '-',
    }

    # UnaryOp(unaryop op, expr operand)
    def visitUnaryOp(self, node):
        self.write("%s "%self.unary_operators[node.op.__class__])
        self.visit(node.operand)

    # Lambda(arguments args, expr body)
    @add_parenthesis
    def visitLambda(self, node):
        self.write('lambda ')
        self.visit(node.args)
        self.write(': ')
        self.visit(node.body)

    # IfExp(expr test, expr body, expr orelse)
    @add_parenthesis
    def visitIfExp(self, node):
        self.visit(node.body)
        self.write(" if ")
        self.visit(node.test)
        self.write(" else ")
        self.visit(node.orelse)

    # Dict(expr* keys, expr* values)
    def visitDict(self, node):
        self.write('{')
        for key, value in zip(node.keys, node.values):
            self.visit(key)
            self.write(': ')
            self.visit(value)
            self.write(', ')
        self.write('}')

    # ListComp(expr elt, comprehension* generators)
    def visitListComp(self, node):
        self.write("[")
        self.visit(node.elt)
        for generator in node.generators:
            # comprehension = (expr target, expr iter, expr* ifs)
            self.write(" for ")
            self.visit(generator.target)
            self.write(" in ")
            self.visit(generator.iter)
            for ifexpr in generator.ifs:
                self.write(" if ")
                self.visit(ifexpr)
        self.write("]")

    # GeneratorExp(expr elt, comprehension* generators)
    def visitGeneratorExp(self, node):
        self.write("(")
        self.visit(node.elt)
        for generator in node.generators:
            # comprehension = (expr target, expr iter, expr* ifs)
            self.write(" for ")
            self.visit(generator.target)
            self.write(" in ")
            self.visit(generator.iter)
            for ifexpr in generator.ifs:
                self.write(" if ")
                self.visit(ifexpr)
        self.write(")")

    # Yield(expr? value)
    def visitYield(self, node):
        self.write("yield")
        if getattr(node, 'value', None):
            self.write(" ")
            self.visit(node.value)

    comparision_operators = {
        _ast.Eq: '==',
        _ast.NotEq: '!=',
        _ast.Lt: '<',
        _ast.LtE: '<=',
        _ast.Gt: '>',
        _ast.GtE: '>=',
        _ast.Is: 'is',
        _ast.IsNot: 'is not',
        _ast.In: 'in',
        _ast.NotIn: 'not in',
    }

    # Compare(expr left, cmpop* ops, expr* comparators)
    @add_parenthesis
    def visitCompare(self, node):
        self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            self.write(" %s "%self.comparision_operators[op.__class__])
            self.visit(comparator)

    # Call(expr func, expr* args, keyword* keywords,
    #                         expr? starargs, expr? kwargs)
    def visitCall(self, node):
        self.visit(node.func)
        self.write("(")
        first = True
        for arg in node.args:
            if not first:
                self.write(', ')
            first = False
            self.visit(arg)

        for keyword in node.keywords:
            if not first:
                self.write(', ')
            first = False
            # keyword = (identifier arg, expr value)
            self.write(keyword.arg)
            self.write('=')
            self.visit(keyword.value)
        if getattr(node, 'starargs', None):
            if not first:
                self.write(', ')
            first = False
            self.write('*')
            self.visit(node.starargs)

        if getattr(node, 'kwargs', None):
            if not first:
                self.write(', ')
            first = False
            self.write('**')
            self.visit(node.kwargs)
        self.write(')')

    # Repr(expr value)
    def visitRepr(self, node):
        self.write('`')
        self.visit(node.value)
        self.write('`')

    # Num(object n)
    def visitNum(self, node):
        self.write(repr(node.n))

    # Str(string s)
    def visitStr(self, node):
        self.write(repr(node.s))

    # Attribute(expr value, identifier attr, expr_context ctx)
    def visitAttribute(self, node):
        self.visit(node.value)
        self.write('.')
        self.write(node.attr)

    # Subscript(expr value, slice slice, expr_context ctx)
    def visitSubscript(self, node):
        self.visit(node.value)
        self.write('[')
        def _process_slice(node):
            if isinstance(node, _ast.Ellipsis):
                self.write('...')
            elif isinstance(node, _ast.Slice):
                if getattr(node, 'lower', 'None'):
                    self.visit(node.lower)
                self.write(':')
                if getattr(node, 'upper', None):
                    self.visit(node.upper)
                if getattr(node, 'step', None):
                    self.write(':')
                    self.visit(node.step)
            elif isinstance(node, _ast.Index):
                self.visit(node.value)
            elif isinstance(node, _ast.ExtSlice):
                self.visit(node.dims[0])
                for dim in node.dims[1:]:
                    self.write(", ")
                    self.visit(dim)
            else:
                raise NotImplemented, 'Slice type not implemented'
        _process_slice(node.slice)
        self.write(']')

    # Name(identifier id, expr_context ctx)
    def visitName(self, node):
        self.write(node.id)

    # List(expr* elts, expr_context ctx)
    def visitList(self, node):
        self.write('[')
        for elt in node.elts:
            self.visit(elt)
            self.write(", ")
        self.write(']')

    # Tuple(expr *elts, expr_context ctx)
    def visitTuple(self, node):
        self.write('(')
        for elt in node.elts:
            self.visit(elt)
            self.write(", ")
        self.write(')')


class ModuleCodeGenerator(CodeGenerator):
    type = 'exec'


class ExpressionCodeGenerator(CodeGenerator):
    type = 'eval'
