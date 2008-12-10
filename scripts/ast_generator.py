#!/usr/bin/env python2.5

"""Script to that automatically generates genshi/templates/_astpy24.py.
Be sure to run this with a Python 2.5 interpreter.
"""

import _ast

done = set()

IGNORE_ATTRS = ('__module__', '__dict__', '__weakref__', '__setattr__',
                '__new__', '__getattribute__', '__reduce__', '__delattr__',
                '__init__')

def print_class(cls):
    bnames = []
    for base in cls.__bases__:
        if base.__module__ == '_ast':
            if base not in done:
                print_class(base)
            bnames.append(base.__name__)
        elif base.__module__ == '__builtin__':
            bnames.append("%s"%base.__name__)
        else:
            bnames.append("%s.%s"%(base.__module__,base.__name__))
    print "class %s(%s):"%(cls.__name__, ", ".join(bnames))
    written = False
    for attr in cls.__dict__:
        if attr not in IGNORE_ATTRS:
            written = True
            print "\t%s = %s"%(attr, repr(cls.__dict__[attr]),)
    if not written:
        print "\tpass"
    done.add(cls)

print "# Generated automatically, please do not edit"
print "# Generator can be found in Genshi SVN, scripts/ast-generator.py"
print
print "__version__ = %s" % _ast.__version__
print

for name in dir(_ast):
    cls = getattr(_ast, name)
    if cls.__class__ is type:
        print_class(cls)
        print
