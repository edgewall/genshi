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

"""Support for using the Python AST on Google App Engine."""

__all__ = ['restore']
__docformat__ = 'restructuredtext en'

def restore(_ast):
    """Gross hack to restore the required classes to the _ast module if it
    appears to be missing them. Stolen from Mako.
    """
    _ast.PyCF_ONLY_AST = 2 << 9
    m = compile("""\
def foo(): pass
foo()
class Bar(object): pass
if False: pass
bar = 'fish'
baz += bar
1 + 2 - 3 * 4 / 5 ** 6
6 // 7 % 8 << 9 >> 10
11 & 12 ^ 13 | 14
15 and 16 or 17
-baz + (not +18) - ~17
baz and 'foo' or 'bar'
(fish is baz == baz) is not baz != fish
fish > baz < fish >= baz <= fish
fish in baz not in fish""", '<unknown>', 'exec', _ast.PyCF_ONLY_AST)
    _ast.Module = type(m)

    for cls in _ast.Module.__mro__:
        if cls.__name__ == 'mod':
            _ast.mod = cls
        elif cls.__name__ == 'AST':
            _ast.AST = cls

    _ast.FunctionDef = type(m.body[0])
    _ast.Call = type(m.body[1].value)
    _ast.ClassDef = type(m.body[2])
    _ast.If = type(m.body[3])

    _ast.Assign = type(m.body[4])
    _ast.Name = type(m.body[4].targets[0])
    _ast.Store = type(m.body[4].targets[0].ctx)
    _ast.Str = type(m.body[4].value)

    _ast.AugAssign = type(m.body[5])
    _ast.Load = type(m.body[5].value.ctx)

    _ast.Sub = type(m.body[6].value.op)
    _ast.Add = type(m.body[6].value.left.op)
    _ast.Div = type(m.body[6].value.right.op)
    _ast.Mult = type(m.body[6].value.right.left.op)
    _ast.Pow = type(m.body[6].value.right.right.op)

    _ast.RShift = type(m.body[7].value.op)
    _ast.LShift = type(m.body[7].value.left.op)
    _ast.Mod = type(m.body[7].value.left.left.op)
    _ast.FloorDiv = type(m.body[7].value.left.left.left.op)

    _ast.BitOr = type(m.body[8].value.op)
    _ast.BitXor = type(m.body[8].value.left.op)
    _ast.BitAnd = type(m.body[8].value.left.left.op)

    _ast.Or = type(m.body[9].value.op)
    _ast.And = type(m.body[9].value.values[0].op)

    _ast.Invert = type(m.body[10].value.right.op)
    _ast.Not = type(m.body[10].value.left.right.op)
    _ast.UAdd = type(m.body[10].value.left.right.operand.op)
    _ast.USub = type(m.body[10].value.left.left.op)

    _ast.Or = type(m.body[11].value.op)
    _ast.And = type(m.body[11].value.values[0].op)

    _ast.IsNot = type(m.body[12].value.ops[0])
    _ast.NotEq = type(m.body[12].value.ops[1])
    _ast.Is = type(m.body[12].value.left.ops[0])
    _ast.Eq = type(m.body[12].value.left.ops[1])

    _ast.Gt = type(m.body[13].value.ops[0])
    _ast.Lt = type(m.body[13].value.ops[1])
    _ast.GtE = type(m.body[13].value.ops[2])
    _ast.LtE = type(m.body[13].value.ops[3])

    _ast.In = type(m.body[14].value.ops[0])
    _ast.NotIn = type(m.body[14].value.ops[1])
