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

"""Basic support for evaluating XPath expressions against streams.

>>> from markup.input import XML
>>> doc = XML('''<doc>
...  <items count="2">
...       <item status="new">
...         <summary>Foo</summary>
...       </item>
...       <item status="closed">
...         <summary>Bar</summary>
...       </item>
...   </items>
... </doc>''')
>>> print doc.select('items/item[@status="closed"]/summary/text()')
Bar

Because the XPath engine operates on markup streams (as opposed to tree
structures), it only implements a subset of the full XPath 1.0 language.
"""

import re

from markup.core import QName, Stream, START, END, TEXT, COMMENT, PI

__all__ = ['Path', 'PathSyntaxError']


class Axis(object):
    """Defines constants for the various supported XPath axes."""

    ATTRIBUTE = 'attribute'
    CHILD = 'child'
    DESCENDANT = 'descendant'
    DESCENDANT_OR_SELF = 'descendant-or-self'
    NAMESPACE = 'namespace'
    SELF = 'self'

    def forname(cls, name):
        """Return the axis constant for the given name, or `None` if no such
        axis was defined.
        """
        return getattr(cls, name.upper().replace('-', '_'), None)
    forname = classmethod(forname)


ATTRIBUTE = Axis.ATTRIBUTE
CHILD = Axis.CHILD
DESCENDANT = Axis.DESCENDANT
DESCENDANT_OR_SELF = Axis.DESCENDANT_OR_SELF
NAMESPACE = Axis.NAMESPACE
SELF = Axis.SELF


class Path(object):
    """Implements basic XPath support on streams.
    
    Instances of this class represent a "compiled" XPath expression, and provide
    methods for testing the path against a stream, as well as extracting a
    substream matching that path.
    """

    def __init__(self, text):
        """Create the path object from a string.
        
        @param text: the path expression
        """
        self.source = text
        self.paths = PathParser(text).parse()

    def __repr__(self):
        paths = []
        for path in self.paths:
            steps = []
            for axis, nodetest, predicates in path:
                steps.append('%s::%s' % (axis, nodetest))
                for predicate in predicates:
                    steps.append('[%s]' % predicate)
            paths.append('/'.join(steps))
        return '<%s "%s">' % (self.__class__.__name__, '|'.join(paths))

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
        `TEXT` event.) Otherwise, it returns `None`.
        
        >>> from markup.input import XML
        >>> xml = XML('<root><elem><child id="1"/></elem><child id="2"/></root>')
        >>> test = Path('child').test()
        >>> for kind, data, pos in xml:
        ...     if test(kind, data, pos):
        ...         print kind, data
        START (u'child', [(u'id', u'1')])
        START (u'child', [(u'id', u'2')])
        """
        paths = [(steps, len(steps), [0]) for steps in self.paths]

        def _test(kind, data, pos):
            for steps, size, stack in paths:
                if not stack:
                    continue
                cursor = stack[-1]

                if kind is END:
                    stack.pop()
                    continue
                elif kind is START:
                    stack.append(cursor)

                while 1:
                    axis, nodetest, predicates = steps[cursor]

                    matched = nodetest(kind, data, pos)
                    if matched and predicates:
                        for predicate in predicates:
                            if not predicate(kind, data, pos):
                                matched = None
                                break

                    if matched:
                        if cursor + 1 == size: # the last location step
                            if ignore_context or \
                                    kind is not START or \
                                    axis in (ATTRIBUTE, NAMESPACE, SELF) or \
                                    len(stack) > 2:
                                return matched
                        else:
                            cursor += 1
                            stack[-1] = cursor

                    if axis is not SELF:
                        break

                if not matched and kind is START \
                               and axis not in (DESCENDANT, DESCENDANT_OR_SELF):
                    # If this step is not a closure, it cannot be matched until
                    # the current element is closed... so we need to move the
                    # cursor back to the previous closure and retest that
                    # against the current element
                    backsteps = [step for step in steps[:cursor]
                                 if step[0] in (DESCENDANT, DESCENDANT_OR_SELF)]
                    backsteps.reverse()
                    for axis, nodetest, predicates in backsteps:
                        matched = nodetest(kind, data, pos)
                        if not matched:
                            cursor -= 1
                        break
                    stack[-1] = cursor

            return None

        return _test


class PathSyntaxError(Exception):
    """Exception raised when an XPath expression is syntactically incorrect."""

    def __init__(self, message, filename=None, lineno=-1, offset=-1):
        if filename:
            message = '%s (%s, line %d)' % (message, filename, lineno)
        Exception.__init__(self, message)
        self.filename = filename
        self.lineno = lineno
        self.offset = offset


class PathParser(object):
    """Tokenizes and parses an XPath expression."""

    _QUOTES = (("'", "'"), ('"', '"'))
    _TOKENS = ('::', ':', '..', '.', '//', '/', '[', ']', '()', '(', ')', '@',
               '=', '!=', '!', '|', ',')
    _tokenize = re.compile('(%s)|([^%s\s]+)|\s+' % (
                           '|'.join([re.escape(t) for t in _TOKENS]),
                           ''.join([re.escape(t[0]) for t in _TOKENS]))).findall

    def __init__(self, text):
        self.tokens = filter(None, [a or b for a, b in self._tokenize(text)])
        self.pos = 0

    # Tokenizer

    at_end = property(lambda self: self.pos == len(self.tokens) - 1)
    cur_token = property(lambda self: self.tokens[self.pos])

    def next_token(self):
        self.pos += 1
        return self.tokens[self.pos]

    def peek_token(self):
        if not self.at_end:
            return self.tokens[self.pos + 1]
        return None

    # Recursive descent parser

    def parse(self):
        """Parses the XPath expression and returns a list of location path
        tests.
        
        For union expressions (such as `*|text()`), this function returns one
        test for each operand in the union. For patch expressions that don't
        use the union operator, the function always returns a list of size 1.
        
        Each path test in turn is a sequence of tests that correspond to the
        location steps, each tuples of the form `(axis, testfunc, predicates)`
        """
        paths = [self._location_path()]
        while self.cur_token == '|':
            self.next_token()
            paths.append(self._location_path())
        if not self.at_end:
            raise PathSyntaxError('Unexpected token %r after end of expression'
                                  % self.cur_token)
        return paths

    def _location_path(self):
        steps = []
        while True:
            if self.cur_token == '//':
                steps.append((DESCENDANT_OR_SELF, NodeTest(), []))
                self.next_token()
            elif self.cur_token == '/' and not steps:
                raise PathSyntaxError('Absolute location paths not supported')

            axis, nodetest, predicates = self._location_step()
            if not axis:
                # The default axis for the first step is "descendant", for other
                # steps it's "child"
                axis = steps and CHILD or DESCENDANT
            steps.append((axis, nodetest, predicates))

            if self.at_end or not self.cur_token.startswith('/'):
                break
            self.next_token()

        return steps

    def _location_step(self):
        if self.cur_token == '@':
            axis = ATTRIBUTE
            self.next_token()
        elif self.cur_token == '.':
            axis = SELF
        elif self.cur_token == '..':
            raise PathSyntaxError('Unsupported axis "parent"')
        elif self.peek_token() == '::':
            axis = Axis.forname(self.cur_token)
            if axis is None:
                raise PathSyntaxError('Unsupport axis "%s"' % axis)
            self.next_token()
            self.next_token()
        else:
            axis = None
        nodetest = self._node_test(axis or CHILD)
        predicates = []
        while self.cur_token == '[':
            predicates.append(self._predicate())
        return axis, nodetest, predicates

    def _node_test(self, axis=None):
        test = None
        if self.peek_token() in ('(', '()'): # Node type test
            test = self._node_type()

        else: # Name test
            if self.cur_token == '*':
                test = PrincipalTypeTest(axis)
            elif self.cur_token == '.':
                test = NodeTest()
            else:
                test = LocalNameTest(axis, self.cur_token)

        if not self.at_end:
            self.next_token()
        return test

    def _node_type(self):
        name = self.cur_token
        self.next_token()

        args = []
        if self.cur_token != '()':
            # The processing-instruction() function optionally accepts the
            # name of the PI as argument, which must be a literal string
            self.next_token() # (
            if self.cur_token != ')':
                string = self.cur_token
                if (string[0], string[-1]) in self._QUOTES:
                    string = string[1:-1]
                args.append(string)

        cls = _nodetest_map.get(name)
        if not cls:
            raise PathSyntaxError('%s() not allowed here' % name)
        return cls(*args)

    def _predicate(self):
        assert self.cur_token == '['
        self.next_token()
        expr = self._or_expr()
        if self.cur_token != ']':
            raise PathSyntaxError('Expected "]" to close predicate, '
                                  'but found "%s"' % self.cur_token)
        if not self.at_end:
            self.next_token()
        return expr

    def _or_expr(self):
        expr = self._and_expr()
        while self.cur_token == 'or':
            self.next_token()
            expr = OrOperator(expr, self._and_expr())
        return expr

    def _and_expr(self):
        expr = self._equality_expr()
        while self.cur_token == 'and':
            self.next_token()
            expr = AndOperator(expr, self._equality_expr())
        return expr

    def _equality_expr(self):
        expr = self._primary_expr()
        while self.cur_token in ('=', '!='):
            op = _operator_map.get(self.cur_token)
            self.next_token()
            expr = op(expr, self._primary_expr())
        return expr

    def _primary_expr(self):
        token = self.cur_token
        if len(token) > 1 and (token[0], token[-1]) in self._QUOTES:
            self.next_token()
            return StringLiteral(token[1:-1])
        elif token[0].isdigit():
            self.next_token()
            return NumberLiteral(float(token))
        elif not self.at_end and self.peek_token().startswith('('):
            if self.next_token() == '()':
                args = []
            else:
                self.next_token()
                args = [self._or_expr()]
                while self.cur_token not in (',', ')'):
                    args.append(self._or_expr())
            self.next_token()
            cls = _function_map.get(token)
            if not cls:
                raise PathSyntaxError('Unsupported function "%s"' % token)
            return cls(*args)
        else:
            axis = None
            if token == '@':
                axis = ATTRIBUTE
                self.next_token()
            return self._node_test(axis)


# Node tests

class PrincipalTypeTest(object):
    __slots__ = ['principal_type']
    def __init__(self, principal_type):
        self.principal_type = principal_type
    def __call__(self, kind, data, pos):
        if kind is START:
            if self.principal_type is ATTRIBUTE:
                return data[1] or None
            else:
                return True
    def __repr__(self):
        return '*'

class LocalNameTest(object):
    __slots__ = ['principal_type', 'name']
    def __init__(self, principal_type, name):
        self.principal_type = principal_type
        self.name = name
    def __call__(self, kind, data, pos):
        if kind is START:
            if self.principal_type is ATTRIBUTE and self.name in data[1]:
                return TEXT, data[1].get(self.name), pos
            else:
                return data[0].localname == self.name
    def __repr__(self):
        return self.name

class CommentNodeTest(object):
    __slots__ = []
    def __call__(self, kind, data, pos):
        return kind is COMMENT and (kind, data, pos)
    def __repr__(self):
        return 'comment()'

class NodeTest(object):
    __slots__ = []
    def __call__(self, kind, data, pos):
        if kind is START:
            return True
        return kind, data, pos
    def __repr__(self):
        return 'node()'

class ProcessingInstructionNodeTest(object):
    __slots__ = ['target']
    def __init__(self, target=None):
        self.target = target
    def __call__(self, kind, data, pos):
        if kind is PI and (not self.target or data[0] == self.target):
            return (kind, data, pos)
    def __repr__(self):
        arg = ''
        if self.target:
            arg = '"' + self.target + '"'
        return 'processing-instruction(%s)' % arg

class TextNodeTest(object):
    __slots__ = []
    def __call__(self, kind, data, pos):
        return kind is TEXT and (kind, data, pos)
    def __repr__(self):
        return 'text()'

_nodetest_map = {'comment': CommentNodeTest, 'node': NodeTest,
                 'processing-instruction': ProcessingInstructionNodeTest,
                 'text': TextNodeTest}

# Functions

class LocalNameFunction(object):
    __slots__ = []
    def __call__(self, kind, data, pos):
        if kind is START:
            return TEXT, data[0].localname, pos
    def __repr__(self):
        return 'local-name()'

class NameFunction(object):
    __slots__ = []
    def __call__(self, kind, data, pos):
        if kind is START:
            return TEXT, data[0], pos
    def __repr__(self):
        return 'name()'

class NamespaceUriFunction(object):
    __slots__ = []
    def __call__(self, kind, data, pos):
        if kind is START:
            return TEXT, data[0].namespace, pos
    def __repr__(self):
        return 'namespace-uri()'

class NotFunction(object):
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos):
        return not self.expr(kind, data, pos)
    def __repr__(self):
        return 'not(%s)' % self.expr

_function_map = {'local-name': LocalNameFunction, 'name': NameFunction,
                 'namespace-uri': NamespaceUriFunction, 'not': NotFunction}

# Literals

class StringLiteral(object):
    __slots__ = ['text']
    def __init__(self, text):
        self.text = text
    def __call__(self, kind, data, pos):
        return TEXT, self.text, (None, -1, -1)
    def __repr__(self):
        return '"%s"' % self.text

class NumberLiteral(object):
    __slots__ = ['number']
    def __init__(self, number):
        self.number = number
    def __call__(self, kind, data, pos):
        return TEXT, unicode(self.number), (None, -1, -1)
    def __repr__(self):
        return str(self.number)

# Operators

class AndOperator(object):
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos):
        lv = self.lval(kind, data, pos)
        if type(lv) is tuple:
            lv = lv[1]
        if not lv:
            return False
        rv = self.rval(kind, data, pos)
        if type(rv) is tuple:
            rv = rv[1]
        return bool(rv)
    def __repr__(self):
        return '%s and %s' % (self.lval, self.rval)

class EqualsOperator(object):
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos):
        lv = self.lval(kind, data, pos)
        if type(lv) is tuple:
            lv = lv[1]
        rv = self.rval(kind, data, pos)
        if type(rv) is tuple:
            rv = rv[1]
        return lv == rv
    def __repr__(self):
        return '%s=%s' % (self.lval, self.rval)

class NotEqualsOperator(object):
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos):
        lv = self.lval(kind, data, pos)
        if type(lv) is tuple:
            lv = lv[1]
        rv = self.rval(kind, data, pos)
        if type(rv) is tuple:
            rv = rv[1]
        return lv != rv
    def __repr__(self):
        return '%s!=%s' % (self.lval, self.rval)

class OrOperator(object):
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos):
        lv = self.lval(kind, data, pos)
        if type(lv) is tuple:
            lv = lv[1]
        if lv:
            return True
        rv = self.rval(kind, data, pos)
        if type(rv) is tuple:
            rv = rv[1]
        return bool(rv)
    def __repr__(self):
        return '%s or %s' % (self.lval, self.rval)

_operator_map = {'=': EqualsOperator, '!=': NotEqualsOperator}
