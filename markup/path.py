# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://markup.cmlenz.net/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://markup.cmlenz.net/log/.

"""Basic support for evaluating XPath expressions against streams."""

import re

from markup.core import QName, Stream

__all__ = ['Path']


class Path(object):
    """Implements basic XPath support on streams.
    
    Instances of this class represent a "compiled" XPath expression, and provide
    methods for testing the path against a stream, as well as extracting a
    substream matching that path.
    """
    _TOKEN_RE = re.compile('(::|\.\.|\(\)|[/.:\[\]\(\)@=!])|'
                           '([^/:\[\]\(\)@=!\s]+)|'
                           '\s+')
    _QUOTES = (("'", "'"), ('"', '"'))

    def __init__(self, text):
        """Create the path object from a string.
        
        @param text: the path expression
        """
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
                        steps[-1] = (False, self._FunctionText(), [])
                    else:
                        raise NotImplementedError('XPath function "%s" not '
                                                  'supported' % cur_tag)
                elif op == '.':
                    steps.append([False, self._CurrentElement(), []])
                else:
                    cur_op += op
                cur_tag = ''
            else:
                closure = cur_op in ('', '//')
                if cur_op == '@':
                    if tag == '*':
                        node_test = self._AnyAttribute()
                    else:
                        node_test = self._AttributeByName(tag)
                else:
                    if tag == '*':
                        node_test = self._AnyChildElement()
                    elif in_predicate:
                        if len(tag) > 1 and (tag[0], tag[-1]) in self._QUOTES:
                            node_test = self._LiteralString(tag[1:-1])
                        if cur_op == '=':
                            node_test = self._OperatorEq(steps[-1][2][-1],
                                                         node_test)
                            steps[-1][2].pop()
                        elif cur_op == '!=':
                            node_test = self._OperatorNeq(steps[-1][2][-1],
                                                          node_test)
                            steps[-1][2].pop()
                    else:
                        node_test = self._ChildElementByName(tag)
                if in_predicate:
                    steps[-1][2].append(node_test)
                else:
                    steps.append([closure, node_test, []])
                cur_op = ''
                cur_tag = tag

        self.steps = []
        for step in steps:
            self.steps.append(tuple(step))

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.source)

    def select(self, stream):
        """Returns a substream of the given stream that matches the path.
        
        If there are no matches, this method returns an empty stream.
        
        >>> from markup.input import XML
        >>> xml = XML('<root><elem><child>Text</child></elem></root>')

        >>> print Path('child').select(xml)
        <child>Text</child>
        
        >>> print Path('child/text()').select(xml)
        Text
        
        @param stream: the stream to select from
        @return: the substream matching the path, or an empty stream
        """
        stream = iter(stream)
        def _generate():
            test = self.test()
            for kind, data, pos in stream:
                result = test(kind, data, pos)
                if result is True:
                    yield kind, data, pos
                    depth = 1
                    while depth > 0:
                        ev = stream.next()
                        depth += {Stream.START: 1, Stream.END: -1}.get(ev[0], 0)
                        yield ev
                        test(*ev)
                elif result:
                    yield result
        return Stream(_generate())

    def test(self, ignore_context=False):
        """Returns a function that can be used to track whether the path matches
        a specific stream event.
        
        The function returned expects the positional arguments `kind`, `data`,
        and `pos`, i.e. basically an unpacked stream event. If the path matches
        the event, the function returns the match (for example, a `START` or
        `TEXT` event.) Otherwise, it returns `None` or `False`.
        
        >>> from markup.input import XML
        >>> xml = XML('<root><elem><child id="1"/></elem><child id="2"/></root>')
        >>> test = Path('child').test()
        >>> for kind, data, pos in xml:
        ...     if test(kind, data, pos):
        ...         print kind, data
        START (u'child', [(u'id', u'1')])
        START (u'child', [(u'id', u'2')])
        """
        stack = [0] # stack of cursors into the location path

        def _test(kind, data, pos):
            if not stack:
                return False

            if kind is Stream.END:
                stack.pop()
                return None

            if kind is Stream.START:
                stack.append(stack[-1])

            matched = False
            closure, node_test, predicates = self.steps[stack[-1]]

            matched = node_test(kind, data, pos)
            if matched and predicates:
                for predicate in predicates:
                    if not predicate(kind, data, pos):
                        matched = None
                        break

            if matched:
                if stack[-1] == len(self.steps) - 1:
                    if ignore_context or len(stack) > 2 \
                                      or node_test.axis != 'child':
                        return matched
                else:
                    stack[-1] += 1

            elif kind is Stream.START and not closure:
                # If this step is not a closure, it cannot be matched until the
                # current element is closed... so we need to move the cursor
                # back to the last closure and retest that against the current
                # element
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

    class _NodeTest(object):
        """Abstract node test."""
        axis = None
        def __repr__(self):
            return '<%s>' % self.__class__.__name__

    class _CurrentElement(_NodeTest):
        """Node test that matches the context node."""
        axis = 'self'
        def __call__(self, kind, *_):
            if kind is Stream.START:
                return True
            return None

    class _AnyChildElement(_NodeTest):
        """Node test that matches any child element."""
        axis = 'child'
        def __call__(self, kind, *_):
            if kind is Stream.START:
                return True
            return None

    class _ChildElementByName(_NodeTest):
        """Node test that matches a child element with a specific tag name."""
        axis = 'child'
        def __init__(self, name):
            self.name = QName(name)
        def __call__(self, kind, data, _):
            if kind is Stream.START:
                return data[0].localname == self.name
            return None
        def __repr__(self):
            return '<%s "%s">' % (self.__class__.__name__, self.name)

    class _AnyAttribute(_NodeTest):
        """Node test that matches any attribute."""
        axis = 'attribute'
        def __call__(self, kind, data, pos):
            if kind is Stream.START:
                text = ''.join([val for _, val in data[1]])
                if text:
                    return Stream.TEXT, text, pos
                return None
            return None

    class _AttributeByName(_NodeTest):
        """Node test that matches an attribute with a specific name."""
        axis = 'attribute'
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

    class _Function(_NodeTest):
        """Abstract node test representing a function."""

    class _FunctionText(_Function):
        """Function that returns text content."""
        def __call__(self, kind, data, pos):
            if kind is Stream.TEXT:
                return kind, data, pos
            return None

    class _LiteralString(_NodeTest):
        """Always returns a literal string."""
        def __init__(self, value):
            self.value = value
        def __call__(self, *_):
            return Stream.TEXT, self.value, (-1, -1)

    class _OperatorEq(_NodeTest):
        """Equality comparison operator."""
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

    class _OperatorNeq(_NodeTest):
        """Inequality comparison operator."""
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
