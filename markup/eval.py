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

from __future__ import division

import __builtin__
from compiler import parse, pycodegen

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
    _visitors = {}

    def __init__(self, source, filename=None, lineno=-1):
        """Create the expression.
        
        @param source: the expression as string
        """
        self.source = source

        ast = parse(self.source, 'eval')
        if isinstance(filename, unicode):
            # pycodegen doesn't like unicode in the filename
            filename = filename.encode('utf-8', 'replace')
        ast.filename = filename or '<string>'
        gen = TemplateExpressionCodeGenerator(ast)
        if lineno >= 0:
            gen.emit('SET_LINENO', lineno)
        self.code = gen.getCode()

    def __repr__(self):
        return '<Expression "%s">' % self.source

    def evaluate(self, data):
        """Evaluate the expression against the given data dictionary.
        
        @param data: a mapping containing the data to evaluate against
        @return: the result of the evaluation
        """
        return eval(self.code)


class TemplateExpressionCodeGenerator(pycodegen.ExpressionCodeGenerator):

    def visitGetattr(self, node):
        """Overridden to fallback to item access if the object doesn't have an
        attribute.
        
        Also, if either method fails, this returns `None` instead of raising an
        `AttributeError`.
        """
        # check whether the object has the request attribute
        self.visit(node.expr)
        self.emit('STORE_NAME', 'obj')
        self.emit('LOAD_GLOBAL', 'hasattr')
        self.emit('LOAD_NAME', 'obj')
        self.emit('LOAD_CONST', node.attrname)
        self.emit('CALL_FUNCTION', 2)
        else_ = self.newBlock()
        self.emit('JUMP_IF_FALSE', else_)
        self.emit('POP_TOP')

        # hasattr returned True, so return the attribute value
        self.emit('LOAD_NAME', 'obj')
        self.emit('LOAD_ATTR', node.attrname)
        self.emit('STORE_NAME', 'val')
        return_ = self.newBlock()
        self.emit('JUMP_FORWARD', return_)

        # hasattr returned False, so try item access
        self.startBlock(else_)
        try_ = self.newBlock()
        except_ = self.newBlock()
        self.emit('SETUP_EXCEPT', except_)
        self.nextBlock(try_)
        self.setups.push((pycodegen.EXCEPT, try_))
        self.emit('LOAD_NAME', 'obj')
        self.emit('LOAD_CONST', node.attrname)
        self.emit('BINARY_SUBSCR')
        self.emit('STORE_NAME', 'val')
        self.emit('POP_BLOCK')
        self.setups.pop()
        self.emit('JUMP_FORWARD', return_)

        # exception handler: just return `None`
        self.startBlock(except_)
        self.emit('DUP_TOP')
        self.emit('LOAD_GLOBAL', 'KeyError')
        self.emit('LOAD_GLOBAL', 'TypeError')
        self.emit('BUILD_TUPLE', 2)
        self.emit('COMPARE_OP', 'exception match')
        next = self.newBlock()
        self.emit('JUMP_IF_FALSE', next)
        self.nextBlock()
        self.emit('POP_TOP')
        self.emit('POP_TOP')
        self.emit('POP_TOP')
        self.emit('POP_TOP')
        self.emit('LOAD_CONST', None) # exception handler body
        self.emit('STORE_NAME', 'val')
        self.emit('JUMP_FORWARD', return_)
        self.nextBlock(next)
        self.emit('POP_TOP')
        self.emit('END_FINALLY')
        
        # return
        self.nextBlock(return_)
        self.emit('LOAD_NAME', 'val')

    def visitName(self, node):
        """Overridden to lookup names in the context data instead of in
        locals/globals.
        
        If a name is not found in the context data, we fall back to Python
        builtins.
        """
        next = self.newBlock()
        end = self.newBlock()

        # default: lookup in context data
        self.loadName('data')
        self.emit('LOAD_ATTR', 'get')
        self.emit('LOAD_CONST', node.name)
        self.emit('CALL_FUNCTION', 1)
        self.emit('STORE_NAME', 'val')

        # test whether the value "is None"
        self.emit('LOAD_NAME', 'val')
        self.emit('LOAD_CONST', None)
        self.emit('COMPARE_OP', 'is')
        self.emit('JUMP_IF_FALSE', next)
        self.emit('POP_TOP')

        # if it is, fallback to builtins
        self.emit('LOAD_GLOBAL', 'getattr')
        self.emit('LOAD_GLOBAL', '__builtin__')
        self.emit('LOAD_CONST', node.name)
        self.emit('LOAD_CONST', None)
        self.emit('CALL_FUNCTION', 3)
        self.emit('STORE_NAME', 'val')
        self.emit('JUMP_FORWARD', end)

        self.nextBlock(next)
        self.emit('POP_TOP')

        self.nextBlock(end)
        self.emit('LOAD_NAME', 'val')

    def visitSubscript(self, node, aug_flag=None):
        """Overridden to fallback to attribute access if the object doesn't
        have an item (or doesn't even support item access).
        
        If either method fails, this returns `None` instead of raising an
        `IndexError`, `KeyError`, or `TypeError`.
        """
        self.visit(node.expr)
        self.emit('STORE_NAME', 'obj')

        if len(node.subs) > 1:
            # For non-scalar subscripts, use the default method
            # FIXME: this should catch exceptions
            self.emit('LOAD_NAME', 'obj')
            for sub in node.subs:
                self.visit(sub)
            self.emit('BUILD_TUPLE', len(node.subs))
            self.emit('BINARY_SUBSCR')

        else:
            # For a scalar subscript, fallback to attribute access
            # FIXME: Would be nice if we could limit this to string subscripts
            try_ = self.newBlock()
            except_ = self.newBlock()
            return_ = self.newBlock()
            self.emit('SETUP_EXCEPT', except_)
            self.nextBlock(try_)
            self.setups.push((pycodegen.EXCEPT, try_))
            self.emit('LOAD_NAME', 'obj')
            self.visit(node.subs[0])
            self.emit('BINARY_SUBSCR')
            self.emit('STORE_NAME', 'val')
            self.emit('POP_BLOCK')
            self.setups.pop()
            self.emit('JUMP_FORWARD', return_)

            self.startBlock(except_)
            self.emit('DUP_TOP')
            self.emit('LOAD_GLOBAL', 'KeyError')
            self.emit('LOAD_GLOBAL', 'IndexError')
            self.emit('LOAD_GLOBAL', 'TypeError')
            self.emit('BUILD_TUPLE', 3)
            self.emit('COMPARE_OP', 'exception match')
            next = self.newBlock()
            self.emit('JUMP_IF_FALSE', next)
            self.nextBlock()
            self.emit('POP_TOP')
            self.emit('POP_TOP')
            self.emit('POP_TOP')
            self.emit('POP_TOP')
            self.emit('LOAD_GLOBAL', 'getattr') # exception handler body
            self.emit('LOAD_NAME', 'obj')
            self.visit(node.subs[0])
            self.emit('LOAD_CONST', None)
            self.emit('CALL_FUNCTION', 3)
            self.emit('STORE_NAME', 'val')
            self.emit('JUMP_FORWARD', return_)
            self.nextBlock(next)
            self.emit('POP_TOP')
            self.emit('END_FINALLY')
        
            # return
            self.nextBlock(return_)
            self.emit('LOAD_NAME', 'val')
