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

try:
    from collections import deque
except ImportError:
    class deque(list):
        def appendleft(self, x): self.insert(0, x)
        def popleft(self): return self.pop(0)
import imp
import os
import re
from StringIO import StringIO

from genshi.core import Attrs, Stream, StreamEventKind, START, TEXT, _ensure
from genshi.template.eval import Expression

__all__ = ['Context', 'Template', 'TemplateError', 'TemplateRuntimeError',
           'TemplateSyntaxError', 'BadDirectiveError']


class TemplateError(Exception):
    """Base exception class for errors related to template processing."""


class TemplateRuntimeError(TemplateError):
    """Exception raised when an the evualation of a Python expression in a
    template causes an error."""

    def __init__(self, message, filename='<string>', lineno=-1, offset=-1):
        self.msg = message
        message = '%s (%s, line %d)' % (self.msg, filename, lineno)
        TemplateError.__init__(self, message)
        self.filename = filename
        self.lineno = lineno
        self.offset = offset


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
        return repr(list(self.frames))

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

    def __init__(self, value, namespaces=None, filename=None, lineno=-1,
                 offset=-1):
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

    def prepare(self, directives, stream):
        """Called after the template stream has been completely parsed.
        
        The part of the template stream associated with the directive will be
        replaced by what this function returns. This allows the directive to
        optimize the template or validate the way the directive is used.
        """
        return stream

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

    def __init__(self, source, basedir=None, filename=None, loader=None,
                 encoding=None):
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
            self.filepath = filename

        self.filters = [self._flatten, self._eval]

        self.stream = list(self._prepare(self._parse(encoding)))

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.filename)

    def _parse(self, encoding):
        """Parse the template.
        
        The parsing stage parses the template and constructs a list of
        directives that will be executed in the render stage. The input is
        split up into literal output (text that does not depend on the context
        data) and directives or expressions.
        """
        raise NotImplementedError

    _FULL_EXPR_RE = re.compile(r'(?<!\$)\$\{(.+?)\}', re.DOTALL)
    _SHORT_EXPR_RE = re.compile(r'(?<!\$)\$([a-zA-Z_][a-zA-Z0-9_\.]*)')

    def _interpolate(cls, text, basedir=None, filename=None, lineno=-1,
                     offset=0):
        """Parse the given string and extract expressions.
        
        This method returns a list containing both literal text and `Expression`
        objects.
        
        @param text: the text to parse
        @param lineno: the line number at which the text was found (optional)
        @param offset: the column number at which the text starts in the source
            (optional)
        """
        filepath = filename
        if filepath and basedir:
            filepath = os.path.join(basedir, filepath)
        def _interpolate(text, patterns, lineno=lineno, offset=offset):
            for idx, grp in enumerate(patterns.pop(0).split(text)):
                if idx % 2:
                    try:
                        yield EXPR, Expression(grp.strip(), filepath, lineno), \
                              (filename, lineno, offset)
                    except SyntaxError, err:
                        raise TemplateSyntaxError(err, filepath, lineno,
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

    def _prepare(self, stream):
        """Call the `prepare` method of every directive instance in the
        template so that various optimization and validation tasks can be
        performed.
        """
        for kind, data, pos in stream:
            if kind is SUB:
                directives, substream = data
                for directive in directives[:]:
                    substream = directive.prepare(directives, substream)
                substream = self._prepare(substream)
                if directives:
                    yield kind, (directives, list(substream)), pos
                else:
                    for event in substream:
                        yield event
            else:
                yield kind, data, pos

    def compile(self):
        """Compile the template to a Python module, and return the module
        object.
        """
        from genshi.template.inline import inline

        name = (self.filename or '_some_ident').replace('.', '_')
        module = imp.new_module(name)
        source = u'\n'.join(list(inline(self)))
        code = compile(source, self.filepath or '<string>', 'exec')
        exec code in module.__dict__, module.__dict__
        return module

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

    def _eval(self, stream, ctxt):
        """Internal stream filter that evaluates any expressions in `START` and
        `TEXT` events.
        """
        filters = (self._flatten, self._eval)

        for kind, data, pos in stream:

            if kind is START and data[1]:
                # Attributes may still contain expressions in start tags at
                # this point, so do some evaluation
                tag, attrs = data
                new_attrs = []
                for name, substream in attrs:
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
                    new_attrs.append((name, u''.join(value)))
                yield kind, (tag, Attrs(new_attrs)), pos

            elif kind is EXPR:
                result = data.evaluate(ctxt)
                if result is not None:
                    # First check for a string, otherwise the iterable test below
                    # succeeds, and the string will be chopped up into individual
                    # characters
                    if isinstance(result, basestring):
                        yield TEXT, result, pos
                    elif hasattr(result, '__iter__'):
                        substream = _ensure(result)
                        for filter_ in filters:
                            substream = filter_(substream, ctxt)
                        for event in substream:
                            yield event
                    else:
                        yield TEXT, unicode(result), pos

            else:
                yield kind, data, pos

    def _flatten(self, stream, ctxt):
        """Internal stream filter that expands `SUB` events in the stream."""
        for event in stream:
            if event[0] is SUB:
                # This event is a list of directives and a list of nested
                # events to which those directives should be applied
                directives, substream = event[1]
                substream = _apply_directives(substream, ctxt, directives)
                for event in self._flatten(substream, ctxt):
                    yield event
            else:
                yield event


EXPR = Template.EXPR
SUB = Template.SUB
