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

"""Implementation of the various template directives."""

import compiler

from genshi.core import Attrs, Stream
from genshi.path import Path
from genshi.template.core import EXPR, Directive, TemplateRuntimeError, \
                                 TemplateSyntaxError, _apply_directives
from genshi.template.eval import Expression, _parse

__all__ = ['AttrsDirective', 'ChooseDirective', 'ContentDirective',
           'DefDirective', 'ForDirective', 'IfDirective', 'MatchDirective',
           'OtherwiseDirective', 'ReplaceDirective', 'StripDirective',
           'WhenDirective', 'WithDirective']


def _assignment(ast):
    """Takes the AST representation of an assignment, and returns a function
    that applies the assignment of a given value to a dictionary.
    """
    def _names(node):
        if isinstance(node, (compiler.ast.AssTuple, compiler.ast.Tuple)):
            return tuple([_names(child) for child in node.nodes])
        elif isinstance(node, (compiler.ast.AssName, compiler.ast.Name)):
            return node.name
    def _assign(data, value, names=_names(ast)):
        if type(names) is tuple:
            for idx in range(len(names)):
                _assign(data, value[idx], names[idx])
        else:
            data[names] = value
    return _assign


class AttrsDirective(Directive):
    """Implementation of the `py:attrs` template directive.
    
    The value of the `py:attrs` attribute should be a dictionary or a sequence
    of `(name, value)` tuples. The items in that dictionary or sequence are
    added as attributes to the element:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:attrs="foo">Bar</li>
    ... </ul>''')
    >>> print tmpl.generate(foo={'class': 'collapse'})
    <ul>
      <li class="collapse">Bar</li>
    </ul>
    >>> print tmpl.generate(foo=[('class', 'collapse')])
    <ul>
      <li class="collapse">Bar</li>
    </ul>
    
    If the value evaluates to `None` (or any other non-truth value), no
    attributes are added:
    
    >>> print tmpl.generate(foo=None)
    <ul>
      <li>Bar</li>
    </ul>
    """
    __slots__ = []

    def __call__(self, stream, ctxt, directives):
        def _generate():
            kind, (tag, attrib), pos  = stream.next()
            attrs = self.expr.evaluate(ctxt)
            if attrs:
                attrib = Attrs(attrib[:])
                if isinstance(attrs, Stream):
                    try:
                        attrs = iter(attrs).next()
                    except StopIteration:
                        attrs = []
                elif not isinstance(attrs, list): # assume it's a dict
                    attrs = attrs.items()
                for name, value in attrs:
                    if value is None:
                        attrib.remove(name)
                    else:
                        attrib.set(name, unicode(value).strip())
            yield kind, (tag, attrib), pos
            for event in stream:
                yield event

        return _apply_directives(_generate(), ctxt, directives)


class ContentDirective(Directive):
    """Implementation of the `py:content` template directive.
    
    This directive replaces the content of the element with the result of
    evaluating the value of the `py:content` attribute:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:content="bar">Hello</li>
    ... </ul>''')
    >>> print tmpl.generate(bar='Bye')
    <ul>
      <li>Bye</li>
    </ul>
    """
    __slots__ = []

    def __call__(self, stream, ctxt, directives):
        def _generate():
            yield stream.next()
            yield EXPR, self.expr, (None, -1, -1)
            event = stream.next()
            for next in stream:
                event = next
            yield event

        return _apply_directives(_generate(), ctxt, directives)


class DefDirective(Directive):
    """Implementation of the `py:def` template directive.
    
    This directive can be used to create "Named Template Functions", which
    are template snippets that are not actually output during normal
    processing, but rather can be expanded from expressions in other places
    in the template.
    
    A named template function can be used just like a normal Python function
    from template expressions:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <p py:def="echo(greeting, name='world')" class="message">
    ...     ${greeting}, ${name}!
    ...   </p>
    ...   ${echo('Hi', name='you')}
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      <p class="message">
        Hi, you!
      </p>
    </div>
    
    If a function does not require parameters, the parenthesis can be omitted
    both when defining and when calling it:
    
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <p py:def="helloworld" class="message">
    ...     Hello, world!
    ...   </p>
    ...   ${helloworld}
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      <p class="message">
        Hello, world!
      </p>
    </div>
    """
    __slots__ = ['name', 'args', 'defaults']

    ATTRIBUTE = 'function'

    def __init__(self, args, namespaces=None, filename=None, lineno=-1,
                 offset=-1):
        Directive.__init__(self, None, namespaces, filename, lineno, offset)
        ast = _parse(args).node
        self.args = []
        self.defaults = {}
        if isinstance(ast, compiler.ast.CallFunc):
            self.name = ast.node.name
            for arg in ast.args:
                if isinstance(arg, compiler.ast.Keyword):
                    self.args.append(arg.name)
                    self.defaults[arg.name] = Expression(arg.expr, filename,
                                                         lineno)
                else:
                    self.args.append(arg.name)
        else:
            self.name = ast.name

    def __call__(self, stream, ctxt, directives):
        stream = list(stream)

        def function(*args, **kwargs):
            scope = {}
            args = list(args) # make mutable
            for name in self.args:
                if args:
                    scope[name] = args.pop(0)
                else:
                    if name in kwargs:
                        val = kwargs.pop(name)
                    else:
                        val = self.defaults.get(name).evaluate(ctxt)
                    scope[name] = val
            ctxt.push(scope)
            for event in _apply_directives(stream, ctxt, directives):
                yield event
            ctxt.pop()
        try:
            function.__name__ = self.name
        except TypeError:
            # Function name can't be set in Python 2.3 
            pass

        # Store the function reference in the bottom context frame so that it
        # doesn't get popped off before processing the template has finished
        # FIXME: this makes context data mutable as a side-effect
        ctxt.frames[-1][self.name] = function

        return []

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.name)


class ForDirective(Directive):
    """Implementation of the `py:for` template directive for repeating an
    element based on an iterable in the context data.
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:for="item in items">${item}</li>
    ... </ul>''')
    >>> print tmpl.generate(items=[1, 2, 3])
    <ul>
      <li>1</li><li>2</li><li>3</li>
    </ul>
    """
    __slots__ = ['assign', 'target', 'filename']

    ATTRIBUTE = 'each'

    def __init__(self, value, namespaces=None, filename=None, lineno=-1,
                 offset=-1):
        if ' in ' not in value:
            raise TemplateSyntaxError('"in" keyword missing in "for" directive',
                                      filename, lineno, offset)
        assign, value = value.split(' in ', 1)
        self.target = _parse(assign, 'exec').node.nodes[0].expr
        self.assign = _assignment(self.target)
        self.filename = filename
        Directive.__init__(self, value.strip(), namespaces, filename, lineno,
                           offset)

    def __call__(self, stream, ctxt, directives):
        iterable = self.expr.evaluate(ctxt)
        if iterable is None:
            return

        assign = self.assign
        scope = {}
        stream = list(stream)
        try:
            iterator = iter(iterable)
            for item in iterator:
                assign(scope, item)
                ctxt.push(scope)
                for event in _apply_directives(stream, ctxt, directives):
                    yield event
                ctxt.pop()
        except TypeError, e:
            raise TemplateRuntimeError(str(e), self.filename, *stream[0][2][1:])

    def __repr__(self):
        return '<%s>' % self.__class__.__name__


class IfDirective(Directive):
    """Implementation of the `py:if` template directive for conditionally
    excluding elements from being output.
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <b py:if="foo">${bar}</b>
    ... </div>''')
    >>> print tmpl.generate(foo=True, bar='Hello')
    <div>
      <b>Hello</b>
    </div>
    """
    __slots__ = []

    ATTRIBUTE = 'test'

    def __call__(self, stream, ctxt, directives):
        if self.expr.evaluate(ctxt):
            return _apply_directives(stream, ctxt, directives)
        return []


class MatchDirective(Directive):
    """Implementation of the `py:match` template directive.

    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <span py:match="greeting">
    ...     Hello ${select('@name')}
    ...   </span>
    ...   <greeting name="Dude" />
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <span>
        Hello Dude
      </span>
    </div>
    """
    __slots__ = ['path', 'namespaces']

    ATTRIBUTE = 'path'

    def __init__(self, value, namespaces=None, filename=None, lineno=-1,
                 offset=-1):
        Directive.__init__(self, None, namespaces, filename, lineno, offset)
        self.path = Path(value, filename, lineno)
        if namespaces is None:
            namespaces = {}
        self.namespaces = namespaces.copy()

    def __call__(self, stream, ctxt, directives):
        ctxt._match_templates.append((self.path.test(ignore_context=True),
                                      self.path, list(stream), self.namespaces,
                                      directives))
        return []

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.path.source)


class ReplaceDirective(Directive):
    """Implementation of the `py:replace` template directive.
    
    This directive replaces the element with the result of evaluating the
    value of the `py:replace` attribute:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <span py:replace="bar">Hello</span>
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      Bye
    </div>
    
    This directive is equivalent to `py:content` combined with `py:strip`,
    providing a less verbose way to achieve the same effect:
    
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <span py:content="bar" py:strip="">Hello</span>
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      Bye
    </div>
    """
    __slots__ = []

    def __call__(self, stream, ctxt, directives):
        yield EXPR, self.expr, (None, -1, -1)


class StripDirective(Directive):
    """Implementation of the `py:strip` template directive.
    
    When the value of the `py:strip` attribute evaluates to `True`, the element
    is stripped from the output
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <div py:strip="True"><b>foo</b></div>
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <b>foo</b>
    </div>
    
    Leaving the attribute value empty is equivalent to a truth value.
    
    This directive is particulary interesting for named template functions or
    match templates that do not generate a top-level element:
    
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <div py:def="echo(what)" py:strip="">
    ...     <b>${what}</b>
    ...   </div>
    ...   ${echo('foo')}
    ... </div>''')
    >>> print tmpl.generate()
    <div>
        <b>foo</b>
    </div>
    """
    __slots__ = []

    def __call__(self, stream, ctxt, directives):
        def _generate():
            if self.expr:
                strip = self.expr.evaluate(ctxt)
            else:
                strip = True
            if strip:
                stream.next() # skip start tag
                previous = stream.next()
                for event in stream:
                    yield previous
                    previous = event
            else:
                for event in stream:
                    yield event

        return _apply_directives(_generate(), ctxt, directives)


class ChooseDirective(Directive):
    """Implementation of the `py:choose` directive for conditionally selecting
    one of several body elements to display.
    
    If the `py:choose` expression is empty the expressions of nested `py:when`
    directives are tested for truth.  The first true `py:when` body is output.
    If no `py:when` directive is matched then the fallback directive
    `py:otherwise` will be used.
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/"
    ...   py:choose="">
    ...   <span py:when="0 == 1">0</span>
    ...   <span py:when="1 == 1">1</span>
    ...   <span py:otherwise="">2</span>
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <span>1</span>
    </div>
    
    If the `py:choose` directive contains an expression, the nested `py:when`
    directives are tested for equality to the `py:choose` expression:
    
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/"
    ...   py:choose="2">
    ...   <span py:when="1">1</span>
    ...   <span py:when="2">2</span>
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <span>2</span>
    </div>
    
    Behavior is undefined if a `py:choose` block contains content outside a
    `py:when` or `py:otherwise` block.  Behavior is also undefined if a
    `py:otherwise` occurs before `py:when` blocks.
    """
    __slots__ = ['matched', 'value']

    ATTRIBUTE = 'test'

    def __call__(self, stream, ctxt, directives):
        frame = dict({'_choose.matched': False})
        if self.expr:
            frame['_choose.value'] = self.expr.evaluate(ctxt)
        ctxt.push(frame)
        for event in _apply_directives(stream, ctxt, directives):
            yield event
        ctxt.pop()


class WhenDirective(Directive):
    """Implementation of the `py:when` directive for nesting in a parent with
    the `py:choose` directive.
    
    See the documentation of `py:choose` for usage.
    """
    __slots__ = ['filename']

    ATTRIBUTE = 'test'

    def __init__(self, value, namespaces=None, filename=None, lineno=-1,
                 offset=-1):
        Directive.__init__(self, value, namespaces, filename, lineno, offset)
        self.filename = filename

    def __call__(self, stream, ctxt, directives):
        matched, frame = ctxt._find('_choose.matched')
        if not frame:
            raise TemplateRuntimeError('"when" directives can only be used '
                                       'inside a "choose" directive',
                                       self.filename, *stream.next()[2][1:])
        if matched:
            return []
        if not self.expr and '_choose.value' not in frame:
            raise TemplateRuntimeError('either "choose" or "when" directive '
                                       'must have a test expression',
                                       self.filename, *stream.next()[2][1:])
        if '_choose.value' in frame:
            value = frame['_choose.value']
            if self.expr:
                matched = value == self.expr.evaluate(ctxt)
            else:
                matched = bool(value)
        else:
            matched = bool(self.expr.evaluate(ctxt))
        frame['_choose.matched'] = matched
        if not matched:
            return []

        return _apply_directives(stream, ctxt, directives)


class OtherwiseDirective(Directive):
    """Implementation of the `py:otherwise` directive for nesting in a parent
    with the `py:choose` directive.
    
    See the documentation of `py:choose` for usage.
    """
    __slots__ = ['filename']

    def __init__(self, value, namespaces=None, filename=None, lineno=-1,
                 offset=-1):
        Directive.__init__(self, None, namespaces, filename, lineno, offset)
        self.filename = filename

    def __call__(self, stream, ctxt, directives):
        matched, frame = ctxt._find('_choose.matched')
        if not frame:
            raise TemplateRuntimeError('an "otherwise" directive can only be '
                                       'used inside a "choose" directive',
                                       self.filename, *stream.next()[2][1:])
        if matched:
            return []
        frame['_choose.matched'] = True

        return _apply_directives(stream, ctxt, directives)


class WithDirective(Directive):
    """Implementation of the `py:with` template directive, which allows
    shorthand access to variables and expressions.
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <span py:with="y=7; z=x+10">$x $y $z</span>
    ... </div>''')
    >>> print tmpl.generate(x=42)
    <div>
      <span>42 7 52</span>
    </div>
    """
    __slots__ = ['vars']

    ATTRIBUTE = 'vars'

    def __init__(self, value, namespaces=None, filename=None, lineno=-1,
                 offset=-1):
        Directive.__init__(self, None, namespaces, filename, lineno, offset)
        self.vars = []
        value = value.strip()
        try:
            ast = _parse(value, 'exec').node
            for node in ast.nodes:
                if isinstance(node, compiler.ast.Discard):
                    continue
                elif not isinstance(node, compiler.ast.Assign):
                    raise TemplateSyntaxError('only assignment allowed in '
                                              'value of the "with" directive',
                                              filename, lineno, offset)
                self.vars.append(([(n, _assignment(n)) for n in node.nodes],
                                  Expression(node.expr, filename, lineno)))
        except SyntaxError, err:
            err.msg += ' in expression "%s" of "%s" directive' % (value,
                                                                  self.tagname)
            raise TemplateSyntaxError(err, filename, lineno,
                                      offset + (err.offset or 0))

    def __call__(self, stream, ctxt, directives):
        frame = {}
        ctxt.push(frame)
        for targets, expr in self.vars:
            value = expr.evaluate(ctxt, nocall=True)
            for _, assign in targets:
                assign(frame, value)
        for event in _apply_directives(stream, ctxt, directives):
            yield event
        ctxt.pop()

    def __repr__(self):
        return '<%s>' % (self.__class__.__name__)
