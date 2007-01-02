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

import compiler
import imp

from genshi.core import Attrs, Stream, _ensure, START, END, TEXT
from genshi.template.core import EXPR, SUB
from genshi.template.directives import *


class CodeWriter(object):

    def __init__(self):
        self.indent = 0

    def __call__(self, line='', *args):
        if not line:
            return ''
        if args:
            line %= args
        return ' ' * self.indent + line

    def shift(self):
        self.indent += 4

    def unshift(self):
        self.indent -= 4


def _expand(obj, pos):
    if obj is not None:
        # First check for a string, otherwise the iterable test below
        # succeeds, and the string will be chopped up into individual
        # characters
        if isinstance(obj, basestring):
            yield TEXT, obj, pos
        elif hasattr(obj, '__iter__'):
            for event in _ensure(obj):
                yield event
        else:
            yield TEXT, unicode(obj), pos

def _expand_text(obj):
    if obj is not None:
        if isinstance(obj, basestring):
            return [obj]
        elif hasattr(obj, '__iter__'):
            return [e[1] for e in _ensure(obj) if e[0] is TEXT]
        else:
            return [unicode(obj)]
    return []

def _assign(ast):
    buf = []
    def _build(node, indices):
        if isinstance(node, (compiler.ast.AssTuple, compiler.ast.Tuple)):
            for idx, child in enumerate(node.nodes):
                _build(child, indices + (idx,))
        elif isinstance(node, (compiler.ast.AssName, compiler.ast.Name)):
            buf.append('%r: v%s' % (node.name, ''.join(['[%s]' % i for i in indices])))
    _build(ast, ())
    return '{%s}' % ', '.join(buf)

def inline(template):
    w = CodeWriter()

    yield w('from genshi.core import Attrs, QName')
    yield w('from genshi.core import START, START_NS, END, END_NS, DOCTYPE, TEXT')
    yield w('from genshi.path import Path')
    yield w('from genshi.template.eval import Expression')
    yield w('from genshi.template.inline import _expand, _expand_text')
    yield w()

    def _predecl_vars(stream):
        for kind, data, pos in stream:

            if kind is START:
                tagname, attrs = data
                yield 'Q', tagname, tagname

                sattrs = Attrs([(n, v) for n, v in attrs
                                if isinstance(v, basestring)])
                for name, val in [(n, v) for n, v in attrs
                                  if not isinstance(v, basestring)]:
                    yield 'Q', name, name
                    for subkind, subdata, subpos in val:
                        if subkind is EXPR:
                            yield 'E', subdata, subdata

                yield 'A', tuple(sattrs), sattrs

            elif kind is EXPR:
                yield 'E', data, data

            elif kind is SUB:
                directives, substream = data
                for directive in directives:

                    if directive.expr:
                        yield 'E', directive.expr, directive.expr

                    elif hasattr(directive, 'vars'):
                        for _, expr in directive.vars:
                            yield 'E', expr, expr

                    elif hasattr(directive, 'path') and directive.path:
                        yield 'P', directive.path, directive.path

                for line in _predecl_vars(substream):
                    yield line

    def _predecl_defs(stream):
        for kind, data, pos in stream:
            if kind is SUB:
                directives, substream = data
                for idx, directive in enumerate(directives):
                    if isinstance(directive, DefDirective):
                        defs.append(directive.name)
                        yield w('def %s:', directive.signature)
                        w.shift()
                        args = ['%r: %s' % (name, name) for name
                                in directive.args]
                        yield w('ctxt.push({%s})', ', '.join(args))
                        for line in _apply(directives[idx + 1:], substream):
                            yield line
                        yield w('ctxt.pop()')
                        w.unshift()

    # Recursively apply directives
    def _apply(directives, stream):
        if not directives:
            for line in _generate(stream):
                yield line
            return

        d = directives[0]
        rest = directives[1:]

        if isinstance(d, DefDirective):
            return # already added

        yield w()
        yield w('# Applying %r', d)

        if isinstance(d, ForDirective):
            yield w('for v in e[%d].evaluate(ctxt):', index['E'][d.expr])
            w.shift()
            yield w('ctxt.push(%s)', _assign(d.target))
            for line in _apply(rest, stream):
                yield line
            yield w('ctxt.pop()')
            w.unshift()

        elif isinstance(d, IfDirective):
            yield w('if e[%d].evaluate(ctxt):', index['E'][d.expr])
            w.shift()
            for line in _apply(rest, stream):
                yield line
            w.unshift()

        else:
            raise NotImplementedError

        yield w()

    # Generate code for the given template stream
    def _generate(stream):
        for kind, data, pos in stream:

            if kind is EXPR:
                yield w('for evt in _expand(e[%d].evaluate(ctxt), (f, %d, %d)): yield evt',
                        index['E'][data], *pos[1:])

            elif kind is START:
                tagname, attrs = data
                qn = index['Q'][tagname]

                sattrs = Attrs([(n, v) for n, v in attrs
                                if isinstance(v, basestring)])
                at = index['A'][tuple(sattrs)]
                if filter(None, [not isinstance(v, basestring) for n,v in attrs]):
                    yield w('at = [(an, "".join(av)) for an, av in ([')
                    w.shift()
                    for name, value in [(n, v) for n, v in attrs
                                        if not isinstance(v, basestring)]:
                        values = []
                        for subkind, subdata, subpos in value:
                            if subkind is EXPR:
                                values.append('_expand_text(e[%d].evaluate(ctxt))' %
                                             index['E'][subdata])
                            elif subkind is TEXT:
                                values.append('[%r]' % subdata)
                        yield w('(q[%d], [v for v in %s if v is not None]),' % (
                            index['Q'][name], ' + '.join(values)
                        ))
                    w.unshift()
                    yield w(']) if av]')
                    yield w('yield START, (q[%d], a[%d] | at), (f, %d, %d)', qn, at,
                            *pos[1:])
                else:
                    yield w('yield START, (q[%d], a[%d]), (f, %d, %d)', qn, at, *pos[1:])

            elif kind is END:
                yield w('yield END, q[%d], (f, %d, %d)', index['Q'][data], *pos[1:])

            elif kind is SUB:
                directives, substream = data
                for line in _apply(directives, substream):
                    yield line

            else:
                yield w('yield %s, %r, (f, %d, %d)', kind, data, *pos[1:])

    yield w('_F = %r', template.filename)
    yield w()

    yield '# predeclare qnames, attributes, and expressions'
    index, counter, values = {}, {}, {}
    for prefix, key, value in _predecl_vars(template.stream):
        if not prefix in counter:
            counter[prefix] = 0
        if key not in index.get(prefix, ()):
            index.setdefault(prefix, {})[key] = counter[prefix]
            counter[prefix] += 1
            values.setdefault(prefix, []).append(value)
    for prefix in sorted(values.keys()):
        yield w('_%s = (', prefix)
        for value in values[prefix]:
            yield w('      ' + repr(value) + ',')
        yield w(')')
    yield w()

    yield w('def generate(ctxt, %s):',
            ', '.join(['f=_F'] + ['%s=_%s' % (n.lower(), n) for n in index]))
    yield w()
    w.shift()

    # Define macro functions
    defs = []
    for line in _predecl_defs(template.stream):
        yield line
    if defs:
        yield w()
        yield w('ctxt.push({%s})', ', '.join(['%r: %s' % (n, n) for n in defs]))
        yield w()

    ei, pi = [0], [0]
    for line in _generate(template.stream):
        yield line


if __name__ == '__main__':
    import timeit
    from genshi.template import Context, MarkupTemplate

    text = """<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:py="http://genshi.edgewall.org/"
      lang="en">
 <body>
    <h1 py:def="sayhi(name='world')" py:strip="">
      Hello, $name!
    </h1>
    ${sayhi()}
    <ul py:if="items">
      <li py:for="idx, item in enumerate(items)"
          class="${idx % 2 and 'odd' or 'even'}">
        <span py:replace="item + 1">NUM</span>
      </li>
    </ul>
 </body>
</html>"""

    ctxt = Context(hello='world', items=range(10))
    tmpl = MarkupTemplate(text)

    print 'Generated source:'
    for idx, line in enumerate(inline(tmpl)):
        print '%3d  %s' % (idx + 1, line)

    print
    print 'Interpreted template:'
    print tmpl.generate(ctxt)

    print
    print 'Executed module:'
    module = tmpl.compile()
    print Stream(module.generate(ctxt))

    print
    print
    t = timeit.Timer('list(tmpl.generate(**data))', '''
from genshi.template import Context, MarkupTemplate
data = dict(hello='world', items=range(10))
tmpl = MarkupTemplate("""%s""")''' % text)
    print 'Interpreted: %.2f msec/pass' % (1000 * t.timeit(number=1000) / 1000)
    print

    t = timeit.Timer('list(module.generate(Context(**data)))', '''
from genshi.core import Stream
from genshi.template import Context, MarkupTemplate
data = dict(hello='world', items=range(10))
tmpl = MarkupTemplate("""%s""")
module = tmpl.compile()''' % text)
    print 'Compiled: %.2f msec/pass' % (1000 * t.timeit(number=1000) / 1000)
    print
