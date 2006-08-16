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

from math import ceil, floor
import re

from markup.core import Stream, START, END, TEXT, COMMENT, PI

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

    def __init__(self, text, filename=None, lineno=-1):
        """Create the path object from a string.
        
        @param text: the path expression
        """
        self.source = text
        self.paths = PathParser(text, filename, lineno).parse()

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
    _tokenize = re.compile('("[^"]*")|(\'[^\']*\')|(%s)|([^%s\s]+)|\s+' % (
                           '|'.join([re.escape(t) for t in _TOKENS]),
                           ''.join([re.escape(t[0]) for t in _TOKENS]))).findall

    def __init__(self, text, filename=None, lineno=-1):
        self.filename = filename
        self.lineno = lineno
        self.tokens = filter(None, [a or b or c or d for a, b, c, d in
                                    self._tokenize(text)])
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
                                  % self.cur_token, self.filename, self.lineno)
        return paths

    def _location_path(self):
        steps = []
        while True:
            if self.cur_token == '//':
                steps.append((DESCENDANT_OR_SELF, NodeTest(), []))
                self.next_token()
            elif self.cur_token == '/' and not steps:
                raise PathSyntaxError('Absolute location paths not supported',
                                      self.filename, self.lineno)

            axis, nodetest, predicates = self._location_step()
            if not axis:
                axis = CHILD
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
            raise PathSyntaxError('Unsupported axis "parent"', self.filename,
                                  self.lineno)
        elif self.peek_token() == '::':
            axis = Axis.forname(self.cur_token)
            if axis is None:
                raise PathSyntaxError('Unsupport axis "%s"' % axis,
                                      self.filename, self.lineno)
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
            raise PathSyntaxError('%s() not allowed here' % name, self.filename,
                                  self.lineno)
        return cls(*args)

    def _predicate(self):
        assert self.cur_token == '['
        self.next_token()
        expr = self._or_expr()
        if self.cur_token != ']':
            raise PathSyntaxError('Expected "]" to close predicate, '
                                  'but found "%s"' % self.cur_token,
                                  self.filename, self.lineno)
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
            return self._function_call()
        else:
            axis = None
            if token == '@':
                axis = ATTRIBUTE
                self.next_token()
            return self._node_test(axis)

    def _function_call(self):
        name = self.cur_token
        if self.next_token() == '()':
            args = []
        else:
            assert self.cur_token == '('
            self.next_token()
            args = [self._or_expr()]
            while self.cur_token == ',':
                self.next_token()
                args.append(self._or_expr())
            if not self.cur_token == ')':
                raise PathSyntaxError('Expected ")" to close function argument '
                                      'list, but found "%s"' % self.cur_token,
                                      self.filename, self.lineno)
        self.next_token()
        cls = _function_map.get(name)
        if not cls:
            raise PathSyntaxError('Unsupported function "%s"' % name,
                                  self.filename, self.lineno)
        return cls(*args)


# Node tests

class PrincipalTypeTest(object):
    """Node test that matches any event with the given principal type."""
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
    """Node test that matches any event with the given prinipal type and
    local name.
    """
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
    """Node test that matches any comment events."""
    __slots__ = []
    def __call__(self, kind, data, pos):
        return kind is COMMENT and (kind, data, pos)
    def __repr__(self):
        return 'comment()'

class NodeTest(object):
    """Node test that matches any node."""
    __slots__ = []
    def __call__(self, kind, data, pos):
        if kind is START:
            return True
        return kind, data, pos
    def __repr__(self):
        return 'node()'

class ProcessingInstructionNodeTest(object):
    """Node test that matches any processing instruction event."""
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
    """Node test that matches any text event."""
    __slots__ = []
    def __call__(self, kind, data, pos):
        return kind is TEXT and (kind, data, pos)
    def __repr__(self):
        return 'text()'

_nodetest_map = {'comment': CommentNodeTest, 'node': NodeTest,
                 'processing-instruction': ProcessingInstructionNodeTest,
                 'text': TextNodeTest}

# Functions

class Function(object):
    """Base class for function nodes in XPath expressions."""

class BooleanFunction(Function):
    """The `boolean` function, which converts its argument to a boolean
    value.
    """
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos):
        val = self.expr(kind, data, pos)
        if type(val) is tuple:
            val = val[1]
        return bool(val)
    def __repr__(self):
        return 'boolean(%r)' % self.expr

class CeilingFunction(Function):
    """The `ceiling` function, which returns the nearest lower integer number
    for the given number.
    """
    __slots__ = ['number']
    def __init__(self, number):
        self.number = number
    def __call__(self, kind, data, pos):
        number = self.number(kind, data, pos)
        if type(number) is tuple:
            number = number[1]
        return ceil(float(number))
    def __repr__(self):
        return 'ceiling(%r)' % self.number

class ConcatFunction(Function):
    """The `concat` function, which concatenates (joins) the variable number of
    strings it gets as arguments.
    """
    __slots__ = ['exprs']
    def __init__(self, *exprs):
        self.exprs = exprs
    def __call__(self, kind, data, pos):
        strings = []
        for item in [expr(kind, data, pos) for expr in self.exprs]:
            if type(item) is tuple:
                assert item[0] is TEXT
                item = item[1]
            strings.append(item)
        return u''.join(strings)
    def __repr__(self):
        return 'concat(%s)' % [repr(expr for expr in self.exprs)]

class ContainsFunction(Function):
    """The `contains` function, which returns whether a string contains a given
    substring.
    """
    __slots__ = ['string1', 'string2']
    def __init__(self, string1, string2):
        self.string1 = string1
        self.string2 = string2
    def __call__(self, kind, data, pos):
        string1 = self.string1(kind, data, pos)
        if type(string1) is tuple:
            string1 = string1[1]
        string2 = self.string2(kind, data, pos)
        if type(string2) is tuple:
            string2 = string2[1]
        return string2 in string1
    def __repr__(self):
        return 'contains(%r, %r)' % (self.string1, self.string2)

class FalseFunction(Function):
    """The `false` function, which always returns the boolean `false` value."""
    __slots__ = []
    def __call__(self, kind, data, pos):
        return False
    def __repr__(self):
        return 'false()'

class FloorFunction(Function):
    """The `ceiling` function, which returns the nearest higher integer number
    for the given number.
    """
    __slots__ = ['number']
    def __init__(self, number):
        self.number = number
    def __call__(self, kind, data, pos):
        number = self.number(kind, data, pos)
        if type(number) is tuple:
            number = number[1]
        return floor(float(number))
    def __repr__(self):
        return 'floor(%r)' % self.number

class LocalNameFunction(Function):
    """The `local-name` function, which returns the local name of the current
    element.
    """
    __slots__ = []
    def __call__(self, kind, data, pos):
        if kind is START:
            return TEXT, data[0].localname, pos
    def __repr__(self):
        return 'local-name()'

class NameFunction(Function):
    """The `name` function, which returns the qualified name of the current
    element.
    """
    __slots__ = []
    def __call__(self, kind, data, pos):
        if kind is START:
            return TEXT, data[0], pos
    def __repr__(self):
        return 'name()'

class NamespaceUriFunction(Function):
    """The `namespace-uri` function, which returns the namespace URI of the
    current element.
    """
    __slots__ = []
    def __call__(self, kind, data, pos):
        if kind is START:
            return TEXT, data[0].namespace, pos
    def __repr__(self):
        return 'namespace-uri()'

class NotFunction(Function):
    """The `not` function, which returns the negated boolean value of its
    argument.
    """
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos):
        return not self.expr(kind, data, pos)
    def __repr__(self):
        return 'not(%s)' % self.expr

class NormalizeSpaceFunction(Function):
    """The `normalize-space` function, which removes leading and trailing
    whitespace in the given string, and replaces multiple adjacent whitespace
    characters inside the string with a single space.
    """
    __slots__ = ['expr']
    _normalize = re.compile(r'\s{2,}').sub
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos):
        string = self.expr(kind, data, pos)
        if type(string) is tuple:
            string = string[1]
        return self._normalize(' ', string.strip())
    def __repr__(self):
        return 'normalize-space(%s)' % repr(self.expr)

class NumberFunction(Function):
    """The `number` function that converts its argument to a number."""
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos):
        val = self.expr(kind, data, pos)
        if type(val) is tuple:
            val = val[1]
        return float(val)
    def __repr__(self):
        return 'number(%r)' % self.expr

class StartsWithFunction(Function):
    """The `starts-with` function that returns whether one string starts with
    a given substring.
    """
    __slots__ = ['string1', 'string2']
    def __init__(self, string1, string2):
        self.string1 = string2
        self.string2 = string2
    def __call__(self, kind, data, pos):
        string1 = self.string1(kind, data, pos)
        if type(string1) is tuple:
            string1 = string1[1]
        string2 = self.string2(kind, data, pos)
        if type(string2) is tuple:
            string2 = string2[1]
        return string1.startswith(string2)
    def __repr__(self):
        return 'starts-with(%r, %r)' % (self.string1, self.string2)

class StringLengthFunction(Function):
    """The `string-length` function that returns the length of the given
    string.
    """
    __slots__ = ['expr']
    def __init__(self, expr):
        self.expr = expr
    def __call__(self, kind, data, pos):
        string = self.expr(kind, data, pos)
        if type(string) is tuple:
            string = string[1]
        return len(string)
    def __repr__(self):
        return 'string-length(%r)' % self.expr

class SubstringFunction(Function):
    """The `substring` function that returns the part of a string that starts
    at the given offset, and optionally limited to the given length.
    """
    __slots__ = ['string', 'start', 'length']
    def __init__(self, string, start, length=None):
        self.string = string
        self.start = start
        self.length = length
    def __call__(self, kind, data, pos):
        string = self.string(kind, data, pos)
        if type(string) is tuple:
            string = string[1]
        start = self.start(kind, data, pos)
        if type(start) is tuple:
            start = start[1]
        length = 0
        if self.length is not None:
            length = self.length(kind, data, pos)
            if type(length) is tuple:
                length = length[1]
        return string[int(start):len(string) - int(length)]
    def __repr__(self):
        if self.length is not None:
            return 'substring(%r, %r, %r)' % (self.string, self.start,
                                              self.length)
        else:
            return 'substring(%r, %r)' % (self.string, self.start)

class SubstringAfterFunction(Function):
    """The `substring-after` function that returns the part of a string that
    is found after the given substring.
    """
    __slots__ = ['string1', 'string2']
    def __init__(self, string1, string2):
        self.string1 = string1
        self.string2 = string2
    def __call__(self, kind, data, pos):
        string1 = self.string1(kind, data, pos)
        if type(string1) is tuple:
            string1 = string1[1]
        string2 = self.string2(kind, data, pos)
        if type(string2) is tuple:
            string2 = string2[1]
        index = string1.find(string2)
        if index >= 0:
            return string1[index + len(string2):]
        return u''
    def __repr__(self):
        return 'substring-after(%r, %r)' % (self.string1, self.string2)

class SubstringBeforeFunction(Function):
    """The `substring-before` function that returns the part of a string that
    is found before the given substring.
    """
    __slots__ = ['string1', 'string2']
    def __init__(self, string1, string2):
        self.string1 = string1
        self.string2 = string2
    def __call__(self, kind, data, pos):
        string1 = self.string1(kind, data, pos)
        if type(string1) is tuple:
            string1 = string1[1]
        string2 = self.string2(kind, data, pos)
        if type(string2) is tuple:
            string2 = string2[1]
        index = string1.find(string2)
        if index >= 0:
            return string1[:index]
        return u''
    def __repr__(self):
        return 'substring-after(%r, %r)' % (self.string1, self.string2)

class TranslateFunction(Function):
    """The `translate` function that translates a set of characters in a
    string to target set of characters.
    """
    __slots__ = ['string', 'fromchars', 'tochars']
    def __init__(self, string, fromchars, tochars):
        self.string = string
        self.fromchars = fromchars
        self.tochars = tochars
    def __call__(self, kind, data, pos):
        string = self.string(kind, data, pos)
        if type(string) is tuple:
            string = string[1]
        fromchars = self.fromchars(kind, data, pos)
        if type(fromchars) is tuple:
            fromchars = fromchars[1]
        tochars = self.tochars(kind, data, pos)
        if type(tochars) is tuple:
            tochars = tochars[1]
        table = dict(zip([ord(c) for c in fromchars],
                         [ord(c) for c in tochars]))
        return string.translate(table)
    def __repr__(self):
        return 'translate(%r, %r, %r)' % (self.string, self.fromchars,
                                          self.tochars)

class TrueFunction(Function):
    """The `true` function, which always returns the boolean `true` value."""
    __slots__ = []
    def __call__(self, kind, data, pos):
        return True
    def __repr__(self):
        return 'true()'

_function_map = {'boolean': BooleanFunction, 'ceiling': CeilingFunction,
                 'concat': ConcatFunction, 'contains': ContainsFunction,
                 'false': FalseFunction, 'floor': FloorFunction,
                 'local-name': LocalNameFunction, 'name': NameFunction,
                 'namespace-uri': NamespaceUriFunction,
                 'normalize-space': NormalizeSpaceFunction, 'not': NotFunction,
                 'number': NumberFunction, 'starts-with': StartsWithFunction,
                 'string-length': StringLengthFunction,
                 'substring': SubstringFunction,
                 'substring-after': SubstringAfterFunction,
                 'substring-before': SubstringBeforeFunction,
                 'translate': TranslateFunction, 'true': TrueFunction}

# Literals

class Literal(object):
    """Abstract base class for literal nodes."""

class StringLiteral(Literal):
    """A string literal node."""
    __slots__ = ['text']
    def __init__(self, text):
        self.text = text
    def __call__(self, kind, data, pos):
        return TEXT, self.text, (None, -1, -1)
    def __repr__(self):
        return '"%s"' % self.text

class NumberLiteral(Literal):
    """A number literal node."""
    __slots__ = ['number']
    def __init__(self, number):
        self.number = number
    def __call__(self, kind, data, pos):
        return TEXT, self.number, (None, -1, -1)
    def __repr__(self):
        return str(self.number)

# Operators

class AndOperator(object):
    """The boolean operator `and`."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos):
        lval = self.lval(kind, data, pos)
        if type(lval) is tuple:
            lval = lval[1]
        if not lval:
            return False
        rval = self.rval(kind, data, pos)
        if type(rval) is tuple:
            rval = rval[1]
        return bool(rval)
    def __repr__(self):
        return '%s and %s' % (self.lval, self.rval)

class EqualsOperator(object):
    """The equality operator `=`."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos):
        lval = self.lval(kind, data, pos)
        if type(lval) is tuple:
            lval = lval[1]
        rval = self.rval(kind, data, pos)
        if type(rval) is tuple:
            rval = rval[1]
        return lval == rval
    def __repr__(self):
        return '%s=%s' % (self.lval, self.rval)

class NotEqualsOperator(object):
    """The equality operator `!=`."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos):
        lval = self.lval(kind, data, pos)
        if type(lval) is tuple:
            lval = lval[1]
        rval = self.rval(kind, data, pos)
        if type(rval) is tuple:
            rval = rval[1]
        return lval != rval
    def __repr__(self):
        return '%s!=%s' % (self.lval, self.rval)

class OrOperator(object):
    """The boolean operator `or`."""
    __slots__ = ['lval', 'rval']
    def __init__(self, lval, rval):
        self.lval = lval
        self.rval = rval
    def __call__(self, kind, data, pos):
        lval = self.lval(kind, data, pos)
        if type(lval) is tuple:
            lval = lval[1]
        if lval:
            return True
        rval = self.rval(kind, data, pos)
        if type(rval) is tuple:
            rval = rval[1]
        return bool(rval)
    def __repr__(self):
        return '%s or %s' % (self.lval, self.rval)

_operator_map = {'=': EqualsOperator, '!=': NotEqualsOperator}
