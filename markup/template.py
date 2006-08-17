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

from markup.core import Attributes, Namespace, Stream, StreamEventKind, _ensure
from markup.core import START, END, START_NS, END_NS, TEXT, COMMENT
from markup.eval import Expression
from markup.input import XMLParser
from markup.path import Path

__all__ = ['BadDirectiveError', 'TemplateError', 'TemplateSyntaxError',
           'TemplateNotFound', 'Template', 'TemplateLoader']


class TemplateError(Exception):
    """Base exception class for errors related to template processing."""


class TemplateSyntaxError(TemplateError):
    """Exception raised when an expression in a template causes a Python syntax
    error."""

    def __init__(self, message, filename='<string>', lineno=-1, offset=-1):
        if isinstance(message, SyntaxError) and message.lineno is not None:
            message = str(message).replace(' (line %d)' % message.lineno, '')
        message = '%s (%s, line %d)' % (message, filename, lineno)
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
        msg = 'bad directive "%s" (%s, line %d)' % (name.localname, filename,
                                                    lineno)
        TemplateSyntaxError.__init__(self, msg, filename, lineno)


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

    def get(self, key):
        """Get a variable's value, starting at the current scope and going
        upward.
        """
        for frame in self.frames:
            if key in frame:
                return frame[key]
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
                                                                  self.name)
            raise TemplateSyntaxError(err, filename, lineno,
                                      offset + (err.offset or 0))

    def __call__(self, stream, ctxt, directives):
        raise NotImplementedError

    def __repr__(self):
        expr = ''
        if self.expr is not None:
            expr = ' "%s"' % self.expr.source
        return '<%s%s>' % (self.__class__.__name__, expr)

    def name(self):
        """Return the local name of the directive as it is used in templates."""
        return self.__class__.__name__.lower().replace('directive', '')
    name = property(name)


def _apply_directives(stream, ctxt, directives):
    """Apply the given directives to the stream."""
    if directives:
        stream = directives[0](iter(stream), ctxt, directives[1:])
    return stream


class AttrsDirective(Directive):
    """Implementation of the `py:attrs` template directive.
    
    The value of the `py:attrs` attribute should be a dictionary. The keys and
    values of that dictionary will be added as attributes to the element:
    
    >>> tmpl = Template('''<ul xmlns:py="http://markup.edgewall.org/">
    ...   <li py:attrs="foo">Bar</li>
    ... </ul>''')
    >>> print tmpl.generate(foo={'class': 'collapse'})
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
                attrib = Attributes(attrib[:])
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
    
    >>> tmpl = Template('''<ul xmlns:py="http://markup.edgewall.org/">
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
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
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
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
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


class ForDirective(Directive):
    """Implementation of the `py:for` template directive for repeating an
    element based on an iterable in the context data.
    
    >>> tmpl = Template('''<ul xmlns:py="http://markup.edgewall.org/">
    ...   <li py:for="item in items">${item}</li>
    ... </ul>''')
    >>> print tmpl.generate(items=[1, 2, 3])
    <ul>
      <li>1</li><li>2</li><li>3</li>
    </ul>
    """
    __slots__ = ['targets']

    ATTRIBUTE = 'each'

    def __init__(self, value, filename=None, lineno=-1, offset=-1):
        targets, value = value.split(' in ', 1)
        self.targets = [str(name.strip()) for name in targets.split(',')]
        Directive.__init__(self, value.strip(), filename, lineno, offset)

    def __call__(self, stream, ctxt, directives):
        iterable = self.expr.evaluate(ctxt)
        if iterable is None:
            return

        scope = {}
        stream = list(stream)
        targets = self.targets
        single = len(targets) == 1
        for item in iter(iterable):
            if single:
                scope[targets[0]] = item
            else:
                for idx, name in enumerate(targets):
                    scope[name] = item[idx]
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
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
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

    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
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
    __slots__ = ['path', 'stream']

    ATTRIBUTE = 'path'

    def __init__(self, value, filename=None, lineno=-1, offset=-1):
        Directive.__init__(self, None, filename, lineno, offset)
        self.path = Path(value, filename, lineno)
        self.stream = []

    def __call__(self, stream, ctxt, directives):
        self.stream = list(stream)
        ctxt._match_templates.append((self.path.test(ignore_context=True),
                                      self.path, self.stream, directives))
        return []

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.path.source)


class ReplaceDirective(Directive):
    """Implementation of the `py:replace` template directive.
    
    This directive replaces the element with the result of evaluating the
    value of the `py:replace` attribute:
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
    ...   <span py:replace="bar">Hello</span>
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      Bye
    </div>
    
    This directive is equivalent to `py:content` combined with `py:strip`,
    providing a less verbose way to achieve the same effect:
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
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
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
    ...   <div py:strip="True"><b>foo</b></div>
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <b>foo</b>
    </div>
    
    Leaving the attribute value empty is equivalent to a truth value.
    
    This directive is particulary interesting for named template functions or
    match templates that do not generate a top-level element:
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
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
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/"
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
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/"
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
        if self.expr:
            self.value = self.expr.evaluate(ctxt)
        self.matched = False
        ctxt.push(dict(_choose=self))
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
        choose = ctxt['_choose']
        if not choose:
            raise TemplateSyntaxError('when directives can only be used inside '
                                      'a choose directive', *stream.next()[2])
        if choose.matched:
            return []
        value = self.expr.evaluate(ctxt)
        try:
            if value == choose.value:
                choose.matched = True
                return _apply_directives(stream, ctxt, directives)
        except AttributeError:
            if value:
                choose.matched = True
                return _apply_directives(stream, ctxt, directives)
        return []


class OtherwiseDirective(Directive):
    """Implementation of the `py:otherwise` directive for nesting in a parent
    with the `py:choose` directive.
    
    See the documentation of `py:choose` for usage.
    """
    def __call__(self, stream, ctxt, directives):
        choose = ctxt['_choose']
        if not choose:
            raise TemplateSyntaxError('an otherwise directive can only be used '
                                      'inside a choose directive',
                                      *stream.next()[2])
        if choose.matched:
            return []
        choose.matched = True
        return _apply_directives(stream, ctxt, directives)


class WithDirective(Directive):
    """Implementation of the `py:with` template directive, which allows
    shorthand access to variables and expressions.
    
    >>> tmpl = Template('''<div xmlns:py="http://markup.edgewall.org/">
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
        try:
            for stmt in value.split(';'):
                name, value = stmt.split('=', 1)
                self.vars.append((name.strip(),
                                  Expression(value.strip(), filename, lineno)))
        except SyntaxError, err:
            raise TemplateSyntaxError(err, filename, lineno,
                                      offset + (err.offset or 0))

    def __call__(self, stream, ctxt, directives):
        ctxt.push(dict([(name, expr.evaluate(ctxt, nocall=True))
                        for name, expr in self.vars]))
        for event in _apply_directives(stream, ctxt, directives):
            yield event
        ctxt.pop()

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__,
                              '; '.join(['%s = %s' % (name, expr.source)
                                         for name, expr in self.vars]))


class Template(object):
    """Can parse a template and transform it into the corresponding output
    based on context data.
    """
    NAMESPACE = Namespace('http://markup.edgewall.org/')

    EXPR = StreamEventKind('EXPR') # an expression
    SUB = StreamEventKind('SUB') # a "subprogram"

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
    _dir_by_name = dict(directives)
    _dir_order = [directive[1] for directive in directives]

    def __init__(self, source, basedir=None, filename=None):
        """Initialize a template from either a string or a file-like object."""
        if isinstance(source, basestring):
            self.source = StringIO(source)
        else:
            self.source = source
        self.basedir = basedir
        self.filename = filename or '<string>'
        if basedir and filename:
            self.filepath = os.path.join(basedir, filename)
        else:
            self.filepath = '<string>'

        self.filters = []
        self.parse()

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.filename)

    def parse(self):
        """Parse the template.
        
        The parsing stage parses the XML template and constructs a list of
        directives that will be executed in the render stage. The input is
        split up into literal output (markup that does not depend on the
        context data) and actual directives (commands or variable
        substitution).
        """
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
                        raise BadDirectiveError(tag, pos[0], pos[1])
                    value = attrib.get(getattr(cls, 'ATTRIBUTE', None), '')
                    directives.append(cls(value, *pos))
                    strip = True

                new_attrib = []
                for name, value in attrib:
                    if name in self.NAMESPACE:
                        cls = self._dir_by_name.get(name.localname)
                        if cls is None:
                            raise BadDirectiveError(name, pos[0], pos[1])
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
                    directives.sort(lambda a, b: cmp(self._dir_order.index(a.__class__),
                                                     self._dir_order.index(b.__class__)))
                    dirmap[(depth, tag)] = (directives, len(stream), strip)

                stream.append((kind, (tag, Attributes(new_attrib)), pos))
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

        self.stream = stream

    _FULL_EXPR_RE = re.compile(r'(?<!\$)\$\{(.+?)\}')
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
            for idx, group in enumerate(patterns.pop(0).split(text)):
                if idx % 2:
                    try:
                        yield EXPR, Expression(group, filename, lineno), \
                              (filename, lineno, offset)
                    except SyntaxError, err:
                        raise TemplateSyntaxError(err, filename, lineno,
                                                  offset + (err.offset or 0))
                elif group:
                    if patterns:
                        for result in _interpolate(group, patterns[:]):
                            yield result
                    else:
                        yield TEXT, group.replace('$$', '$'), \
                              (filename, lineno, offset)
                if '\n' in group:
                    lines = group.splitlines()
                    lineno += len(lines) - 1
                    offset += len(lines[-1])
                else:
                    offset += len(group)
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
            assert isinstance(ctxt, Context)
        else:
            ctxt = Context(**kwargs)

        stream = self.stream
        for filter_ in [self._eval, self._match, self._flatten] + self.filters:
            stream = filter_(iter(stream), ctxt)
        return Stream(stream)

    def _eval(self, stream, ctxt=None):
        """Internal stream filter that evaluates any expressions in `START` and
        `TEXT` events.
        """
        filters = (self._eval, self._match)

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
                        for subkind, subdata, subpos in substream:
                            if subkind is EXPR:
                                values.append(subdata.evaluate(ctxt))
                            else:
                                values.append(subdata)
                        value = [unicode(x) for x in values if x is not None]
                        if not value:
                            continue
                    new_attrib.append((name, u''.join(value)))
                yield kind, (tag, Attributes(new_attrib)), pos

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
                        substream = _ensure(result)
                        for filter_ in filters:
                            substream = filter_(substream, ctxt)
                        for event in substream:
                            yield event
                    except TypeError:
                        # Neither a string nor an iterable, so just pass it
                        # through
                        yield TEXT, unicode(result), pos

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
                for filter_ in (self._eval, self._match, self._flatten):
                    substream = filter_(substream, ctxt)
                for event in substream:
                    yield event
            else:
                yield kind, data, pos

    def _match(self, stream, ctxt=None, match_templates=None):
        """Internal stream filter that applies any defined match templates
        to the stream.
        """
        if match_templates is None:
            match_templates = ctxt._match_templates

        for kind, data, pos in stream:

            # We (currently) only care about start and end events for matching
            # We might care about namespace events in the future, though
            if not match_templates or kind not in (START, END):
                yield kind, data, pos
                continue

            for idx, (test, path, template, directives) in \
                    enumerate(match_templates):

                if test(kind, data, pos) is True:
                    # Consume and store all events until an end event
                    # corresponding to this start event is encountered
                    content = [(kind, data, pos)]
                    depth = 1
                    while depth > 0:
                        kind, data, pos = stream.next()
                        if kind is START:
                            depth += 1
                        elif kind is END:
                            depth -= 1
                        content.append((kind, data, pos))
                        test(kind, data, pos)

                    content = list(self._flatten(content, ctxt))
                    select = lambda path: Stream(content).select(path)
                    ctxt.push(dict(select=select))

                    template = _apply_directives(template, ctxt, directives)
                    for event in self._match(self._eval(template, ctxt),
                                             ctxt, match_templates[:idx] +
                                             match_templates[idx + 1:]):
                        yield event

                    ctxt.pop()
                    break

            else: # no matches
                yield kind, data, pos


EXPR = Template.EXPR
SUB = Template.SUB


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
    >>> isinstance(template, Template)
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

    def load(self, filename, relative_to=None):
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
        """
        from markup.filters import IncludeFilter

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

        for dirname in search_path:
            filepath = os.path.join(dirname, filename)
            try:
                fileobj = open(filepath, 'U')
                try:
                    tmpl = Template(fileobj, basedir=dirname, filename=filename)
                    tmpl.filters.append(IncludeFilter(self))
                finally:
                    fileobj.close()
                self._cache[filename] = tmpl
                self._mtime[filename] = os.path.getmtime(filepath)
                return tmpl
            except IOError:
                continue
        raise TemplateNotFound(filename, self.search_path)
