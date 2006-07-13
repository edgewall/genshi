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

"""Basic support for evaluating XPath expressions against streams."""

import re

from markup.core import QName, Stream, START, END, TEXT

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
                        steps[-1] = (False, self._function_text(), [])
                    else:
                        raise NotImplementedError('XPath function "%s" not '
                                                  'supported' % cur_tag)
                elif op == '.':
                    steps.append([False, self._node_test_current_element(), []])
                else:
                    cur_op += op
                cur_tag = ''
            else:
                closure = cur_op in ('', '//')
                if cur_op == '@':
                    if tag == '*':
                        node_test = self._node_test_any_attribute()
                    else:
                        node_test = self._node_test_attribute_by_name(tag)
                else:
                    if tag == '*':
                        node_test = self._node_test_any_child_element()
                    elif in_predicate:
                        if len(tag) > 1 and (tag[0], tag[-1]) in self._QUOTES:
                            node_test = self._literal_string(tag[1:-1])
                        if cur_op == '=':
                            node_test = self._operator_eq(steps[-1][2][-1],
                                                          node_test)
                            steps[-1][2].pop()
                        elif cur_op == '!=':
                            node_test = self._operator_neq(steps[-1][2][-1],
                                                           node_test)
                            steps[-1][2].pop()
                    else:
                        node_test = self._node_test_child_element_by_name(tag)
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
                        subkind, subdata, subpos = stream.next()
                        if subkind is START:
                            depth += 1
                        elif subkind is END:
                            depth -= 1
                        yield subkind, subdata, subpos
                        test(subkind, subdata, subpos)
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
        from markup.core import END, START
        stack = [0] # stack of cursors into the location path

        def _test(kind, data, pos):
            if not stack:
                return False
            cursor = stack[-1]

            if kind is END:
                stack.pop()
                return None

            elif kind is START:
                stack.append(cursor)

            matched = False
            closure, node_test, predicates = self.steps[cursor]

            matched = node_test(kind, data, pos)
            if matched and predicates:
                for predicate in predicates:
                    if not predicate(kind, data, pos):
                        matched = None
                        break

            if matched:
                if cursor == len(self.steps) - 1:
                    if ignore_context or len(stack) > 2 \
                                      or node_test.axis != 'child':
                        return matched
                else:
                    stack[-1] += 1

            elif kind is START and not closure:
                # If this step is not a closure, it cannot be matched until the
                # current element is closed... so we need to move the cursor
                # back to the last closure and retest that against the current
                # element
                closures = [step for step in self.steps[:cursor] if step[0]]
                closures.reverse()
                for closure, node_test, predicates in closures:
                    cursor -= 1
                    if closure:
                        matched = node_test(kind, data, pos)
                        if matched:
                            cursor += 1
                        break
                stack[-1] = cursor

            return None

        return _test

    def _node_test_current_element(self):
        def _test(kind, *_):
            return kind is START
        _test.axis = 'self'
        return _test

    def _node_test_any_child_element(self):
        def _test(kind, *_):
            return kind is START
        _test.axis = 'child'
        return _test

    def _node_test_child_element_by_name(self, name):
        def _test(kind, data, _):
            return kind is START and data[0].localname == name
        _test.axis = 'child'
        return _test

    def _node_test_any_attribute(self):
        def _test(kind, data, _):
            if kind is START and data[1]:
                return data[1]
        _test.axis = 'attribute'
        return _test

    def _node_test_attribute_by_name(self, name):
        def _test(kind, data, pos):
            if kind is START and name in data[1]:
                return TEXT, data[1].get(name), pos
        _test.axis = 'attribute'
        return _test

    def _function_text(self):
        def _test(kind, data, pos):
            return kind is TEXT and (kind, data, pos)
        _test.axis = None
        return _test

    def _literal_string(self, text):
        def _test(*_):
            return TEXT, text, (None, -1, -1)
        _test.axis = None
        return _test

    def _operator_eq(self, lval, rval):
        def _test(kind, data, pos):
            lv = lval(kind, data, pos)
            rv = rval(kind, data, pos)
            return (lv and lv[1]) == (rv and rv[1])
        _test.axis = None
        return _test

    def _operator_neq(self, lval, rval):
        def _test(kind, data, pos):
            lv = lval(kind, data, pos)
            rv = rval(kind, data, pos)
            return (lv and lv[1]) != (rv and rv[1])
        _test.axis = None
        return _test
