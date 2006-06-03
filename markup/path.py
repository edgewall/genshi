# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.

"""Basic support for evaluating XPath expressions against streams."""

import re

from markup.core import QName, Stream

__all__ = ['Path']

_QUOTES = (("'", "'"), ('"', '"'))

class Path(object):
    """Basic XPath support on markup event streams.
    
    >>> from markup.input import XML
    
    Selecting specific tags:
    
    >>> Path('root').select(XML('<root/>')).render()
    '<root/>'
    >>> Path('//root').select(XML('<root/>')).render()
    '<root/>'
    
    Using wildcards for tag names:
    
    >>> Path('*').select(XML('<root/>')).render()
    '<root/>'
    >>> Path('//*').select(XML('<root/>')).render()
    '<root/>'
    
    Selecting attribute values:
    
    >>> Path('@foo').select(XML('<root/>')).render()
    ''
    >>> Path('@foo').select(XML('<root foo="bar"/>')).render()
    'bar'
    
    Selecting descendants:
    
    >>> Path("root/*").select(XML('<root><foo/><bar/></root>')).render()
    '<foo/><bar/>'
    >>> Path("root/bar").select(XML('<root><foo/><bar/></root>')).render()
    '<bar/>'
    >>> Path("root/baz").select(XML('<root><foo/><bar/></root>')).render()
    ''
    >>> Path("root/foo/*").select(XML('<root><foo><bar/></foo></root>')).render()
    '<bar/>'
    
    Selecting text nodes:
    >>> Path("item/text()").select(XML('<root><item>Foo</item></root>')).render()
    'Foo'
    >>> Path("item/text()").select(XML('<root><item>Foo</item><item>Bar</item></root>')).render()
    'FooBar'
    
    Skipping ancestors:
    
    >>> Path("foo/bar").select(XML('<root><foo><bar/></foo></root>')).render()
    '<bar/>'
    >>> Path("foo/*").select(XML('<root><foo><bar/></foo></root>')).render()
    '<bar/>'
    >>> Path("root/bar").select(XML('<root><foo><bar/></foo></root>')).render()
    ''
    >>> Path("root/bar").select(XML('<root><foo><bar id="1"/></foo><bar id="2"/></root>')).render()
    '<bar id="2"/>'
    >>> Path("root/*/bar").select(XML('<root><foo><bar/></foo></root>')).render()
    '<bar/>'
    >>> Path("root//bar").select(XML('<root><foo><bar id="1"/></foo><bar id="2"/></root>')).render()
    '<bar id="1"/><bar id="2"/>'
    >>> Path("root//bar").select(XML('<root><foo><bar id="1"/></foo><bar id="2"/></root>')).render()
    '<bar id="1"/><bar id="2"/>'
    
    Using simple attribute predicates:
    >>> Path("root/item[@important]").select(XML('<root><item/><item important="very"/></root>')).render()
    '<item important="very"/>'
    >>> Path('root/item[@important="very"]').select(XML('<root><item/><item important="very"/></root>')).render()
    '<item important="very"/>'
    >>> Path("root/item[@important='very']").select(XML('<root><item/><item important="notso"/></root>')).render()
    ''
    >>> Path("root/item[@important!='very']").select(
    ...     XML('<root><item/><item important="notso"/></root>')).render()
    '<item/><item important="notso"/>'
    """

    _TOKEN_RE = re.compile('(::|\.\.|\(\)|[/.:\[\]\(\)@=!])|'
                           '([^/:\[\]\(\)@=!\s]+)|'
                           '\s+')

    def __init__(self, text):
        self.source = text

        steps = []
        cur_op = ''
        cur_tag = ''
        in_predicate = False
        for op, tag in self._TOKEN_RE.findall(text):
            if op:
                if op == '[':
                    in_predicate = True
                elif op == ']':
                    in_predicate = False
                elif op.startswith('('):
                    if cur_tag == 'text':
                        steps[-1] = (False, self.fn_text(), [])
                    else:
                        raise NotImplementedError('XPath function "%s" not '
                                                  'supported' % cur_tag)
                else:
                    cur_op += op
                cur_tag = ''
            else:
                closure = cur_op in ('', '//')
                if cur_op == '@':
                    if tag == '*':
                        node_test = self.any_attribute()
                    else:
                        node_test = self.attribute_by_name(tag)
                else:
                    if tag == '*':
                        node_test = self.any_element()
                    elif in_predicate:
                        if len(tag) > 1 and (tag[0], tag[-1]) in _QUOTES:
                            node_test = self.literal_string(tag[1:-1])
                        if cur_op == '=':
                            node_test = self.op_eq(steps[-1][2][-1], node_test)
                            steps[-1][2].pop()
                        elif cur_op == '!=':
                            node_test = self.op_neq(steps[-1][2][-1], node_test)
                            steps[-1][2].pop()
                    else:
                        node_test = self.element_by_name(tag)
                if in_predicate:
                    steps[-1][2].append(node_test)
                else:
                    steps.append([closure, node_test, []])
                cur_op = ''
                cur_tag = tag
        self.steps = steps

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.source)

    def select(self, stream):
        stream = iter(stream)
        def _generate(tests):
            test = self.test()
            for kind, data, pos in stream:
                result = test(kind, data, pos)
                if result is True:
                    yield kind, data, pos
                    depth = 1
                    while depth > 0:
                        ev = stream.next()
                        if ev[0] is Stream.START:
                            depth += 1
                        elif ev[0] is Stream.END:
                            depth -= 1
                        yield ev
                        test(*ev)
                elif result:
                    yield result
        return Stream(_generate(self.steps))

    def test(self):
        stack = [0] # stack of cursors into the location path

        def _test(kind, data, pos):
            #print '\nTracker %r test [%s] %r' % (self, kind, data)

            if not stack:
                return False

            if kind is Stream.END:
                stack.pop()
                return None

            if kind is Stream.START:
                stack.append(stack[-1])

            matched = False
            closure, node_test, predicates = self.steps[stack[-1]]

            #print '  Testing against %r' % node_test
            matched = node_test(kind, data, pos)
            if matched and predicates:
                for predicate in predicates:
                    if not predicate(kind, data, pos):
                        matched = None
                        break

            if matched:
                if stack[-1] == len(self.steps) - 1:
                    #print '  Last step %r... returned %r' % (node_test, matched)
                    return matched

                #print '  Matched intermediate step %r... proceed to next step %r' % (node_test, self.steps[stack[-1] + 1])
                stack[-1] += 1

            elif kind is Stream.START and not closure:
                # FIXME: If this step is not a closure, it cannot be matched
                #        until the current element is closed... so we need to
                #        move the cursor back to the last closure and retest
                #        that against the current element
                closures = [step for step in self.steps[:stack[-1]] if step[0]]
                closures.reverse()
                for closure, node_test, predicates in closures:
                    stack[-1] -= 1
                    if closure:
                        matched = node_test(kind, data, pos)
                        if matched:
                            stack[-1] += 1
                        break

            return None

        return _test

    class any_element(object):
        def __call__(self, kind, data, pos):
            if kind is Stream.START:
                return True
            return None
        def __repr__(self):
            return '<%s>' % self.__class__.__name__

    class element_by_name(object):
        def __init__(self, name):
            self.name = QName(name)
        def __call__(self, kind, data, pos):
            if kind is Stream.START:
                return data[0].localname == self.name
            return None
        def __repr__(self):
            return '<%s "%s">' % (self.__class__.__name__, self.name)

    class any_attribute(object):
        def __call__(self, kind, data, pos):
            if kind is Stream.START:
                text = ''.join([val for name, val in data[1]])
                if text:
                    return Stream.TEXT, text, pos
                return None
            return None
        def __repr__(self):
            return '<%s>' % (self.__class__.__name__)

    class attribute_by_name(object):
        def __init__(self, name):
            self.name = QName(name)
        def __call__(self, kind, data, pos):
            if kind is Stream.START:
                if self.name in data[1]:
                    return Stream.TEXT, data[1].get(self.name), pos
                return None
            return None
        def __repr__(self):
            return '<%s "%s">' % (self.__class__.__name__, self.name)

    class fn_text(object):
        def __call__(self, kind, data, pos):
            if kind is Stream.TEXT:
                return kind, data, pos
            return None
        def __repr__(self):
            return '<%s>' % (self.__class__.__name__)

    class literal_string(object):
        def __init__(self, value):
            self.value = value
        def __call__(self, kind, data, pos):
            return Stream.TEXT, self.value, (-1, -1)
        def __repr__(self):
            return '<%s>' % (self.__class__.__name__)

    class op_eq(object):
        def __init__(self, lval, rval):
            self.lval = lval
            self.rval = rval
        def __call__(self, kind, data, pos):
            lval = self.lval(kind, data, pos)
            rval = self.rval(kind, data, pos)
            return (lval and lval[1]) == (rval and rval[1])
        def __repr__(self):
            return '<%s %r = %r>' % (self.__class__.__name__, self.lval,
                                     self.rval)

    class op_neq(object):
        def __init__(self, lval, rval):
            self.lval = lval
            self.rval = rval
        def __call__(self, kind, data, pos):
            lval = self.lval(kind, data, pos)
            rval = self.rval(kind, data, pos)
            return (lval and lval[1]) != (rval and rval[1])
        def __repr__(self):
            return '<%s %r != %r>' % (self.__class__.__name__, self.lval,
                                      self.rval)
