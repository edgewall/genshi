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

"""Implementation of the template engine."""

try:
    from collections import deque
except ImportError:
    class deque(list):
        def appendleft(self, x): self.insert(0, x)
        def popleft(self): return self.pop(0)
import compiler
import os
import re
from StringIO import StringIO

from genshi.core import Attrs, Namespace, Stream, StreamEventKind, _ensure
from genshi.core import START, END, START_NS, END_NS, TEXT, COMMENT
from genshi.eval import Expression
from genshi.input import XMLParser
from genshi.path import Path

__all__ = ['BadDirectiveError', 'TemplateError', 'TemplateSyntaxError',
           'TemplateNotFound', 'MarkupTemplate', 'TextTemplate',
           'TemplateLoader']


class TemplateError(Exception):
    """Base exception class for errors related to template processing."""


class TemplateSyntaxError(TemplateError):
    """Exception raised when an expression in a template causes a Python syntax
    error."""

    def __init__(self, message, filename='<string>', lineno=-1, offset=-1):
        if isinstance(message, SyntaxError) and message.lineno is not None:
            message = str(message).replace(' (line %d)' % message.lineno, '')
        self.msg = message
        message = '%s (%s, line %d)' % (self.msg, filename, lineno)
        TemplateError.__init__(self, message)
        self.filename = filename
        self.lineno = lineno
        self.offset = offset


class BadDirectiveError(TemplateSyntaxError):
    """Exception raised when an unknown directive is encountered when parsing
    a template.
    
    An unknown directive is any attribute using the namespace for directives,
    with a local name that doesn't match any registered directive.
    """

    def __init__(self, name, filename='<string>', lineno=-1):
        message = 'bad directive "%s"' % name
        TemplateSyntaxError.__init__(self, message, filename, lineno)


class TemplateNotFound(TemplateError):
    """Exception raised when a specific template file could not be found."""

    def __init__(self, name, search_path):
        TemplateError.__init__(self, 'Template "%s" not found' % name)
        self.search_path = search_path


class Context(object):
    """Container for template input data.
    
    A context provides a stack of scopes (represented by dictionaries).
    
    Template directives such as loops can push a new scope on the stack with
    data that should only be available inside the loop. When the loop
    terminates, that scope can get popped off the stack again.
    
    >>> ctxt = Context(one='foo', other=1)
    >>> ctxt.get('one')
    'foo'
    >>> ctxt.get('other')
    1
    >>> ctxt.push(dict(one='frost'))
    >>> ctxt.get('one')
    'frost'
    >>> ctxt.get('other')
    1
    >>> ctxt.pop()
    {'one': 'frost'}
    >>> ctxt.get('one')
    'foo'
    """

    def __init__(self, **data):
        self.frames = deque([data])
        self.pop = self.frames.popleft
        self.push = self.frames.appendleft
        self._match_templates = []

    def __repr__(self):
        return repr(self.frames)

    def __setitem__(self, key, value):
        """Set a variable in the current scope."""
        self.frames[0][key] = value

    def _find(self, key, default=None):
        """Retrieve a given variable's value and the frame it was found in.

        Intented for internal use by directives.
        """
        for frame in self.frames:
            if key in frame:
                return frame[key], frame
        return default, None

    def get(self, key, default=None):
        """Get a variable's value, starting at the current scope and going
        upward.
        """
        for frame in self.frames:
            if key in frame:
                return frame[key]
        return default
    __getitem__ = get

    def push(self, data):
        """Push a new scope on the stack."""

    def pop(self):
        """Pop the top-most scope from the stack."""


class Directive(object):
    """Abstract base class for template directives.
    
    A directive is basically a callable that takes three positional arguments:
    `ctxt` is the template data context, `stream` is an iterable over the
    events that the directive applies to, and `directives` is is a list of
    other directives on the same stream that need to be applied.
    
    Directives can be "anonymous" or "registered". Registered directives can be
    applied by the template author using an XML attribute with the
    corresponding name in the template. Such directives should be subclasses of
    this base class that can  be instantiated with the value of the directive
    attribute as parameter.
    
    Anonymous directives are simply functions conforming to the protocol
    described above, and can only be applied programmatically (for example by
    template filters).
    """
    __slots__ = ['expr']

    def __init__(self, value, filename=None, lineno=-1, offset=-1):
        try:
            self.expr = value and Expression(value, filename, lineno) or None
        except SyntaxError, err:
            err.msg += ' in expression "%s" of "%s" directive' % (value,
                                                                  self.tagname)
            raise TemplateSyntaxError(err, filename, lineno,
                                      offset + (err.offset or 0))

    def __call__(self, stream, ctxt, directives):
        raise NotImplementedError

    def __repr__(self):
        expr = ''
        if self.expr is not None:
            expr = ' "%s"' % self.expr.source
        return '<%s%s>' % (self.__class__.__name__, expr)

    def tagname(self):
        """Return the local tag name of the directive as it is used in
        templates.
        """
        return self.__class__.__name__.lower().replace('directive', '')
    tagname = property(tagname)


def _apply_directives(stream, ctxt, directives):
    """Apply the given directives to the stream."""
    if directives:
        stream = directives[0](iter(stream), ctxt, directives[1:])
    return stream

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
            kind, data, pos = stream.next()
            if kind is START:
                yield kind, data, pos # emit start tag
            yield EXPR, self.expr, pos
            previous = stream.next()
            for event in stream:
                previous = event
            if previous is not None:
                yield previous

        return _apply_directives(_generate(), ctxt, directives)


class DefDirective(Directive):
    """Implementation of the `py:def` template directive.
    
    This directive can be used to create "Named Template Functions", which
    are template snippets that are not actually output during normal
    processing, but rather can be expanded from expressions in other places
    in the template.
    
    A named template function can be used just like a normal Python function
    from template expressions:
    
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

    def __init__(self, args, filename=None, lineno=-1, offset=-1):
        Directive.__init__(self, None, filename, lineno, offset)
        ast = compiler.parse(args, 'eval').node
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
        ctxt.frames[-1][self.name] = function

        return []

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.name)


class ForDirective(Directive):
    """Implementation of the `py:for` template directive for repeating an
    element based on an iterable in the context data.
    
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:for="item in items">${item}</li>
    ... </ul>''')
    >>> print tmpl.generate(items=[1, 2, 3])
    <ul>
      <li>1</li><li>2</li><li>3</li>
    </ul>
    """
    __slots__ = ['assign']

    ATTRIBUTE = 'each'

    def __init__(self, value, filename=None, lineno=-1, offset=-1):
        if ' in ' not in value:
            raise TemplateSyntaxError('"in" keyword missing in "for" directive',
                                      filename, lineno, offset)
        assign, value = value.split(' in ', 1)
        ast = compiler.parse(assign, 'exec')
        self.assign = _assignment(ast.node.nodes[0].expr)
        Directive.__init__(self, value.strip(), filename, lineno, offset)

    def __call__(self, stream, ctxt, directives):
        iterable = self.expr.evaluate(ctxt)
        if iterable is None:
            return

        assign = self.assign
        scope = {}
        stream = list(stream)
        for item in iter(iterable):
            assign(scope, item)
            ctxt.push(scope)
            for event in _apply_directives(stream, ctxt, directives):
                yield event
            ctxt.pop()

    def __repr__(self):
        return '<%s "%s in %s">' % (self.__class__.__name__,
                                    ', '.join(self.targets), self.expr.source)


class IfDirective(Directive):
    """Implementation of the `py:if` template directive for conditionally
    excluding elements from being output.
    
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
    __slots__ = ['path']

    ATTRIBUTE = 'path'

    def __init__(self, value, filename=None, lineno=-1, offset=-1):
        Directive.__init__(self, None, filename, lineno, offset)
        self.path = Path(value, filename, lineno)

    def __call__(self, stream, ctxt, directives):
        ctxt._match_templates.append((self.path.test(ignore_context=True),
                                      self.path, list(stream), directives))
        return []

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.path.source)


class ReplaceDirective(Directive):
    """Implementation of the `py:replace` template directive.
    
    This directive replaces the element with the result of evaluating the
    value of the `py:replace` attribute:
    
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
        kind, data, pos = stream.next()
        yield EXPR, self.expr, pos


class StripDirective(Directive):
    """Implementation of the `py:strip` template directive.
    
    When the value of the `py:strip` attribute evaluates to `True`, the element
    is stripped from the output
    
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

    ATTRIBUTE = 'test'

    def __call__(self, stream, ctxt, directives):
        matched, frame = ctxt._find('_choose.matched')
        if not frame:
            raise TemplateSyntaxError('"when" directives can only be used '
                                      'inside a "choose" directive',
                                      *stream.next()[2])
        if matched:
            return []
        if not self.expr:
            raise TemplateSyntaxError('"when" directive has no test condition',
                                      *stream.next()[2])
        value = self.expr.evaluate(ctxt)
        if '_choose.value' in frame:
            matched = (value == frame['_choose.value'])
        else:
            matched = bool(value)
        frame['_choose.matched'] = matched
        if not matched:
            return []

        return _apply_directives(stream, ctxt, directives)


class OtherwiseDirective(Directive):
    """Implementation of the `py:otherwise` directive for nesting in a parent
    with the `py:choose` directive.
    
    See the documentation of `py:choose` for usage.
    """
    def __call__(self, stream, ctxt, directives):
        matched, frame = ctxt._find('_choose.matched')
        if not frame:
            raise TemplateSyntaxError('an "otherwise" directive can only be '
                                      'used inside a "choose" directive',
                                      *stream.next()[2])
        if matched:
            return []
        frame['_choose.matched'] = True

        return _apply_directives(stream, ctxt, directives)


class WithDirective(Directive):
    """Implementation of the `py:with` template directive, which allows
    shorthand access to variables and expressions.
    
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

    def __init__(self, value, filename=None, lineno=-1, offset=-1):
        Directive.__init__(self, None, filename, lineno, offset)
        self.vars = []
        value = value.strip()
        try:
            ast = compiler.parse(value, 'exec').node
            for node in ast.nodes:
                if isinstance(node, compiler.ast.Discard):
                    continue
                elif not isinstance(node, compiler.ast.Assign):
                    raise TemplateSyntaxError('only assignment allowed in '
                                              'value of the "with" directive',
                                              filename, lineno, offset)
                self.vars.append(([_assignment(n) for n in node.nodes],
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
            for assign in targets:
                assign(frame, value)
        for event in _apply_directives(stream, ctxt, directives):
            yield event
        ctxt.pop()

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__,
                              '; '.join(['%s = %s' % (name, expr.source)
                                         for name, expr in self.vars]))


class TemplateMeta(type):
    """Meta class for templates."""

    def __new__(cls, name, bases, d):
        if 'directives' in d:
            d['_dir_by_name'] = dict(d['directives'])
            d['_dir_order'] = [directive[1] for directive in d['directives']]

        return type.__new__(cls, name, bases, d)


class Template(object):
    """Abstract template base class.
    
    This class implements most of the template processing model, but does not
    specify the syntax of templates.
    """
    __metaclass__ = TemplateMeta

    EXPR = StreamEventKind('EXPR') # an expression
    SUB = StreamEventKind('SUB') # a "subprogram"

    def __init__(self, source, basedir=None, filename=None, loader=None):
        """Initialize a template from either a string or a file-like object."""
        if isinstance(source, basestring):
            self.source = StringIO(source)
        else:
            self.source = source
        self.basedir = basedir
        self.filename = filename
        if basedir and filename:
            self.filepath = os.path.join(basedir, filename)
        else:
            self.filepath = None

        self.filters = [self._flatten, self._eval]

        self.stream = self._parse()

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.filename)

    def _parse(self):
        """Parse the template.
        
        The parsing stage parses the template and constructs a list of
        directives that will be executed in the render stage. The input is
        split up into literal output (text that does not depend on the context
        data) and directives or expressions.
        """
        raise NotImplementedError

    _FULL_EXPR_RE = re.compile(r'(?<!\$)\$\{(.+?)\}', re.DOTALL)
    _SHORT_EXPR_RE = re.compile(r'(?<!\$)\$([a-zA-Z][a-zA-Z0-9_\.]*)')

    def _interpolate(cls, text, filename=None, lineno=-1, offset=-1):
        """Parse the given string and extract expressions.
        
        This method returns a list containing both literal text and `Expression`
        objects.
        
        @param text: the text to parse
        @param lineno: the line number at which the text was found (optional)
        @param offset: the column number at which the text starts in the source
            (optional)
        """
        def _interpolate(text, patterns, filename=filename, lineno=lineno,
                         offset=offset):
            for idx, grp in enumerate(patterns.pop(0).split(text)):
                if idx % 2:
                    try:
                        yield EXPR, Expression(grp.strip(), filename, lineno), \
                              (filename, lineno, offset)
                    except SyntaxError, err:
                        raise TemplateSyntaxError(err, filename, lineno,
                                                  offset + (err.offset or 0))
                elif grp:
                    if patterns:
                        for result in _interpolate(grp, patterns[:]):
                            yield result
                    else:
                        yield TEXT, grp.replace('$$', '$'), \
                              (filename, lineno, offset)
                if '\n' in grp:
                    lines = grp.splitlines()
                    lineno += len(lines) - 1
                    offset += len(lines[-1])
                else:
                    offset += len(grp)
        return _interpolate(text, [cls._FULL_EXPR_RE, cls._SHORT_EXPR_RE])
    _interpolate = classmethod(_interpolate)

    def generate(self, *args, **kwargs):
        """Apply the template to the given context data.
        
        Any keyword arguments are made available to the template as context
        data.
        
        Only one positional argument is accepted: if it is provided, it must be
        an instance of the `Context` class, and keyword arguments are ignored.
        This calling style is used for internal processing.
        
        @return: a markup event stream representing the result of applying
            the template to the context data.
        """
        if args:
            assert len(args) == 1
            ctxt = args[0]
            if ctxt is None:
                ctxt = Context(**kwargs)
            assert isinstance(ctxt, Context)
        else:
            ctxt = Context(**kwargs)

        stream = self.stream
        for filter_ in self.filters:
            stream = filter_(iter(stream), ctxt)
        return Stream(stream)

    def _eval(self, stream, ctxt=None):
        """Internal stream filter that evaluates any expressions in `START` and
        `TEXT` events.
        """
        filters = (self._flatten, self._eval)

        for kind, data, pos in stream:

            if kind is START and data[1]:
                # Attributes may still contain expressions in start tags at
                # this point, so do some evaluation
                tag, attrib = data
                new_attrib = []
                for name, substream in attrib:
                    if isinstance(substream, basestring):
                        value = substream
                    else:
                        values = []
                        for subkind, subdata, subpos in self._eval(substream,
                                                                   ctxt):
                            if subkind is TEXT:
                                values.append(subdata)
                        value = [x for x in values if x is not None]
                        if not value:
                            continue
                    new_attrib.append((name, u''.join(value)))
                yield kind, (tag, Attrs(new_attrib)), pos

            elif kind is EXPR:
                result = data.evaluate(ctxt)
                if result is None:
                    continue

                # First check for a string, otherwise the iterable test below
                # succeeds, and the string will be chopped up into individual
                # characters
                if isinstance(result, basestring):
                    yield TEXT, result, pos
                else:
                    # Test if the expression evaluated to an iterable, in which
                    # case we yield the individual items
                    try:
                        substream = _ensure(iter(result))
                    except TypeError:
                        # Neither a string nor an iterable, so just pass it
                        # through
                        yield TEXT, unicode(result), pos
                    else:
                        for filter_ in filters:
                            substream = filter_(substream, ctxt)
                        for event in substream:
                            yield event

            else:
                yield kind, data, pos

    def _flatten(self, stream, ctxt=None):
        """Internal stream filter that expands `SUB` events in the stream."""
        for kind, data, pos in stream:
            if kind is SUB:
                # This event is a list of directives and a list of nested
                # events to which those directives should be applied
                directives, substream = data
                substream = _apply_directives(substream, ctxt, directives)
                for event in self._flatten(substream, ctxt):
                    yield event
            else:
                yield kind, data, pos

    def _match(self, stream, ctxt=None, match_templates=None):
        """Internal stream filter that applies any defined match templates
        to the stream.
        """
        if match_templates is None:
            match_templates = ctxt._match_templates
        nsprefix = {} # mapping of namespace prefixes to URIs

        tail = []
        def _strip(stream):
            depth = 1
            while 1:
                kind, data, pos = stream.next()
                if kind is START:
                    depth += 1
                elif kind is END:
                    depth -= 1
                if depth > 0:
                    yield kind, data, pos
                else:
                    tail[:] = [(kind, data, pos)]
                    break

        for kind, data, pos in stream:

            # We (currently) only care about start and end events for matching
            # We might care about namespace events in the future, though
            if not match_templates or kind not in (START, END):
                yield kind, data, pos
                continue

            for idx, (test, path, template, directives) in \
                    enumerate(match_templates):

                if test(kind, data, pos, nsprefix, ctxt) is True:

                    # Let the remaining match templates know about the event so
                    # they get a chance to update their internal state
                    for test in [mt[0] for mt in match_templates[idx + 1:]]:
                        test(kind, data, pos, nsprefix, ctxt)

                    # Consume and store all events until an end event
                    # corresponding to this start event is encountered
                    content = [(kind, data, pos)]
                    content += list(self._match(_strip(stream), ctxt)) + tail

                    kind, data, pos = tail[0]
                    for test in [mt[0] for mt in match_templates]:
                        test(kind, data, pos, nsprefix, ctxt)

                    # Make the select() function available in the body of the
                    # match template
                    def select(path):
                        return Stream(content).select(path)
                    ctxt.push(dict(select=select))

                    # Recursively process the output
                    template = _apply_directives(template, ctxt, directives)
                    for event in self._match(self._eval(self._flatten(template,
                                                                      ctxt),
                                                        ctxt), ctxt,
                                             match_templates[:idx] +
                                             match_templates[idx + 1:]):
                        yield event

                    ctxt.pop()
                    break

            else: # no matches
                yield kind, data, pos


EXPR = Template.EXPR
SUB = Template.SUB


class MarkupTemplate(Template):
    """Implementation of the template language for XML-based templates.
    
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:for="item in items">${item}</li>
    ... </ul>''')
    >>> print tmpl.generate(items=[1, 2, 3])
    <ul>
      <li>1</li><li>2</li><li>3</li>
    </ul>
    """
    NAMESPACE = Namespace('http://genshi.edgewall.org/')

    directives = [('def', DefDirective),
                  ('match', MatchDirective),
                  ('when', WhenDirective),
                  ('otherwise', OtherwiseDirective),
                  ('for', ForDirective),
                  ('if', IfDirective),
                  ('choose', ChooseDirective),
                  ('with', WithDirective),
                  ('replace', ReplaceDirective),
                  ('content', ContentDirective),
                  ('attrs', AttrsDirective),
                  ('strip', StripDirective)]

    def __init__(self, source, basedir=None, filename=None, loader=None):
        """Initialize a template from either a string or a file-like object."""
        Template.__init__(self, source, basedir=basedir, filename=filename,
                          loader=loader)

        self.filters.append(self._match)
        if loader:
            from genshi.filters import IncludeFilter
            self.filters.append(IncludeFilter(loader))

    def _parse(self):
        """Parse the template from an XML document."""
        stream = [] # list of events of the "compiled" template
        dirmap = {} # temporary mapping of directives to elements
        ns_prefix = {}
        depth = 0

        for kind, data, pos in XMLParser(self.source, filename=self.filename):

            if kind is START_NS:
                # Strip out the namespace declaration for template directives
                prefix, uri = data
                if uri == self.NAMESPACE:
                    ns_prefix[prefix] = uri
                else:
                    stream.append((kind, data, pos))

            elif kind is END_NS:
                if data in ns_prefix:
                    del ns_prefix[data]
                else:
                    stream.append((kind, data, pos))

            elif kind is START:
                # Record any directive attributes in start tags
                tag, attrib = data
                directives = []
                strip = False

                if tag in self.NAMESPACE:
                    cls = self._dir_by_name.get(tag.localname)
                    if cls is None:
                        raise BadDirectiveError(tag.localname, pos[0], pos[1])
                    value = attrib.get(getattr(cls, 'ATTRIBUTE', None), '')
                    directives.append(cls(value, *pos))
                    strip = True

                new_attrib = []
                for name, value in attrib:
                    if name in self.NAMESPACE:
                        cls = self._dir_by_name.get(name.localname)
                        if cls is None:
                            raise BadDirectiveError(name.localname, pos[0],
                                                    pos[1])
                        directives.append(cls(value, *pos))
                    else:
                        if value:
                            value = list(self._interpolate(value, *pos))
                            if len(value) == 1 and value[0][0] is TEXT:
                                value = value[0][1]
                        else:
                            value = [(TEXT, u'', pos)]
                        new_attrib.append((name, value))

                if directives:
                    index = self._dir_order.index
                    directives.sort(lambda a, b: cmp(index(a.__class__),
                                                     index(b.__class__)))
                    dirmap[(depth, tag)] = (directives, len(stream), strip)

                stream.append((kind, (tag, Attrs(new_attrib)), pos))
                depth += 1

            elif kind is END:
                depth -= 1
                stream.append((kind, data, pos))

                # If there have have directive attributes with the corresponding
                # start tag, move the events inbetween into a "subprogram"
                if (depth, data) in dirmap:
                    directives, start_offset, strip = dirmap.pop((depth, data))
                    substream = stream[start_offset:]
                    if strip:
                        substream = substream[1:-1]
                    stream[start_offset:] = [(SUB, (directives, substream),
                                              pos)]

            elif kind is TEXT:
                for kind, data, pos in self._interpolate(data, *pos):
                    stream.append((kind, data, pos))

            elif kind is COMMENT:
                if not data.lstrip().startswith('!'):
                    stream.append((kind, data, pos))

            else:
                stream.append((kind, data, pos))

        return stream

    def _match(self, stream, ctxt=None, match_templates=None):
        """Internal stream filter that applies any defined match templates
        to the stream.
        """
        if match_templates is None:
            match_templates = ctxt._match_templates
        nsprefix = {} # mapping of namespace prefixes to URIs

        tail = []
        def _strip(stream):
            depth = 1
            while 1:
                kind, data, pos = stream.next()
                if kind is START:
                    depth += 1
                elif kind is END:
                    depth -= 1
                if depth > 0:
                    yield kind, data, pos
                else:
                    tail[:] = [(kind, data, pos)]
                    break

        for kind, data, pos in stream:

            # We (currently) only care about start and end events for matching
            # We might care about namespace events in the future, though
            if not match_templates or kind not in (START, END):
                yield kind, data, pos
                continue

            for idx, (test, path, template, directives) in \
                    enumerate(match_templates):

                if test(kind, data, pos, nsprefix, ctxt) is True:

                    # Let the remaining match templates know about the event so
                    # they get a chance to update their internal state
                    for test in [mt[0] for mt in match_templates[idx + 1:]]:
                        test(kind, data, pos, nsprefix, ctxt)

                    # Consume and store all events until an end event
                    # corresponding to this start event is encountered
                    content = [(kind, data, pos)]
                    content += list(self._match(_strip(stream), ctxt)) + tail

                    kind, data, pos = tail[0]
                    for test in [mt[0] for mt in match_templates]:
                        test(kind, data, pos, nsprefix, ctxt)

                    # Make the select() function available in the body of the
                    # match template
                    def select(path):
                        return Stream(content).select(path)
                    ctxt.push(dict(select=select))

                    # Recursively process the output
                    template = _apply_directives(template, ctxt, directives)
                    for event in self._match(self._eval(self._flatten(template,
                                                                      ctxt),
                                                        ctxt), ctxt,
                                             match_templates[:idx] +
                                             match_templates[idx + 1:]):
                        yield event

                    ctxt.pop()
                    break

            else: # no matches
                yield kind, data, pos


class TextTemplate(Template):
    """Implementation of a simple text-based template engine.
    
    >>> tmpl = TextTemplate('''Dear $name,
    ... 
    ... We have the following items for you:
    ... #for item in items
    ...  * $item
    ... #end
    ... 
    ... All the best,
    ... Foobar''')
    >>> print tmpl.generate(name='Joe', items=[1, 2, 3]).render('text')
    Dear Joe,
    <BLANKLINE>
    We have the following items for you:
     * 1
     * 2
     * 3
    <BLANKLINE>
    All the best,
    Foobar
    """
    directives = [('def', DefDirective),
                  ('when', WhenDirective),
                  ('otherwise', OtherwiseDirective),
                  ('for', ForDirective),
                  ('if', IfDirective),
                  ('choose', ChooseDirective),
                  ('with', WithDirective)]

    _DIRECTIVE_RE = re.compile(r'^\s*(?<!\\)#((?:\w+|#).*)\n?', re.MULTILINE)

    def _parse(self):
        """Parse the template from text input."""
        stream = [] # list of events of the "compiled" template
        dirmap = {} # temporary mapping of directives to elements
        depth = 0

        source = self.source.read()
        offset = 0
        lineno = 1

        for idx, mo in enumerate(self._DIRECTIVE_RE.finditer(source)):
            start, end = mo.span()
            if start > offset:
                text = source[offset:start]
                for kind, data, pos in self._interpolate(text, self.filename,
                                                         lineno, 0):
                    stream.append((kind, data, pos))
                lineno += len(text.splitlines())

            text = source[start:end].lstrip()[1:]
            lineno += len(text.splitlines())
            directive = text.split(None, 1)
            if len(directive) > 1:
                command, value = directive
            else:
                command, value = directive[0], None

            if command == 'end':
                depth -= 1
                if depth in dirmap:
                    directive, start_offset = dirmap.pop(depth)
                    substream = stream[start_offset:]
                    stream[start_offset:] = [(SUB, ([directive], substream),
                                              (self.filename, lineno, 0))]
            elif command != '#':
                cls = self._dir_by_name.get(command)
                if cls is None:
                    raise BadDirectiveError(command)
                directive = cls(value, self.filename, lineno, 0)
                dirmap[depth] = (directive, len(stream))
                depth += 1

            offset = end

        if offset < len(source):
            text = source[offset:].replace('\\#', '#')
            for kind, data, pos in self._interpolate(text, self.filename,
                                                     lineno, 0):
                stream.append((kind, data, pos))

        return stream


class TemplateLoader(object):
    """Responsible for loading templates from files on the specified search
    path.
    
    >>> import tempfile
    >>> fd, path = tempfile.mkstemp(suffix='.html', prefix='template')
    >>> os.write(fd, '<p>$var</p>')
    11
    >>> os.close(fd)
    
    The template loader accepts a list of directory paths that are then used
    when searching for template files, in the given order:
    
    >>> loader = TemplateLoader([os.path.dirname(path)])
    
    The `load()` method first checks the template cache whether the requested
    template has already been loaded. If not, it attempts to locate the
    template file, and returns the corresponding `Template` object:
    
    >>> template = loader.load(os.path.basename(path))
    >>> isinstance(template, MarkupTemplate)
    True
    
    Template instances are cached: requesting a template with the same name
    results in the same instance being returned:
    
    >>> loader.load(os.path.basename(path)) is template
    True
    
    >>> os.remove(path)
    """
    def __init__(self, search_path=None, auto_reload=False):
        """Create the template laoder.
        
        @param search_path: a list of absolute path names that should be
            searched for template files
        @param auto_reload: whether to check the last modification time of
            template files, and reload them if they have changed
        """
        self.search_path = search_path
        if self.search_path is None:
            self.search_path = []
        self.auto_reload = auto_reload
        self._cache = {}
        self._mtime = {}

    def load(self, filename, relative_to=None, cls=MarkupTemplate):
        """Load the template with the given name.
        
        If the `filename` parameter is relative, this method searches the search
        path trying to locate a template matching the given name. If the file
        name is an absolute path, the search path is not bypassed.
        
        If requested template is not found, a `TemplateNotFound` exception is
        raised. Otherwise, a `Template` object is returned that represents the
        parsed template.
        
        Template instances are cached to avoid having to parse the same
        template file more than once. Thus, subsequent calls of this method
        with the same template file name will return the same `Template`
        object (unless the `auto_reload` option is enabled and the file was
        changed since the last parse.)
        
        If the `relative_to` parameter is provided, the `filename` is
        interpreted as being relative to that path.
        
        @param filename: the relative path of the template file to load
        @param relative_to: the filename of the template from which the new
            template is being loaded, or `None` if the template is being loaded
            directly
        @param cls: the class of the template object to instantiate
        """
        if relative_to:
            filename = os.path.join(os.path.dirname(relative_to), filename)
        filename = os.path.normpath(filename)

        # First check the cache to avoid reparsing the same file
        try:
            tmpl = self._cache[filename]
            if not self.auto_reload or \
                    os.path.getmtime(tmpl.filepath) == self._mtime[filename]:
                return tmpl
        except KeyError:
            pass

        # Bypass the search path if the filename is absolute
        search_path = self.search_path
        if os.path.isabs(filename):
            search_path = [os.path.dirname(filename)]

        if not search_path:
            raise TemplateError('Search path for templates not configured')

        for dirname in search_path:
            filepath = os.path.join(dirname, filename)
            try:
                fileobj = open(filepath, 'U')
                try:
                    tmpl = cls(fileobj, basedir=dirname, filename=filename,
                               loader=self)
                finally:
                    fileobj.close()
                self._cache[filename] = tmpl
                self._mtime[filename] = os.path.getmtime(filepath)
                return tmpl
            except IOError:
                continue

        raise TemplateNotFound(filename, self.search_path)
