# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""A filter for generalised functional-style transformations of markup streams,
inspired by JQuery.

For example, the following transformation removes the ``<title>`` element from
the ``<head>`` of the input document:

>>> html = HTML('<html><head><title>Some Title</title></head>'
...             '<body>Some <em>body</em> text.</body></html>')
>>> print html | Transformer('head/title').remove()
<html><head/><body>Some <em>body</em> text.</body></html>

The ``Transformer`` support a large number of useful transformations out of the
box, but custom transformations can be added easily.
"""

import sys

from genshi.path import Path
from genshi.builder import Element
from genshi.core import Stream, Attrs, QName, TEXT, START, END

__all__ = ['Transformer', 'Injector', 'ENTER', 'EXIT', 'INSIDE', 'OUTSIDE']


class TransformMark(str):
    """A mark on a transformation stream."""
    __slots__ = []
    _instances = {}

    def __new__(cls, val):
        return cls._instances.setdefault(val, str.__new__(cls, val))


ENTER = TransformMark('ENTER')
"""Stream augmentation mark indicating that a selected range of events is being
entered."""

INSIDE = TransformMark('INSIDE')
"""Stream augmentation mark indicating that processing is currently inside a
selected range of events."""

OUTSIDE = TransformMark('OUTSIDE')
"""Stream augmentation mark indicating that processing is currently outside any
selected range of events."""

EXIT = TransformMark('EXIT')
"""Stream augmentation mark indicating that a selected range of events is being
exited."""


class Transformer(object):
    """Stream filter that can apply a variety of different transformations to
    a stream.

    This is achieved by selecting the events to be transformed using XPath,
    then applying the transformations to the events matched by the path
    expression. Each marked event is in the form (mark, (kind, data, pos)),
    where mark can be any of `ENTER`, `EXIT`, `INSIDE`, `OUTSIDE` or None.

    The first three marks match `START` and `END` events, and any events
    contained `INSIDE` any selected XML/HTML element. A non-element match
    outside a `START`/`END` container (e.g. ``text()``) will yield an `OUTSIDE`
    mark.

    >>> html = HTML('<html><head><title>Some Title</title></head>'
    ...             '<body>Some <em>body</em> text.</body></html>')

    Transformations act on selected stream events matching an XPath. Here's an
    example of removing some markup (title) selected by an expression:

    >>> print html | Transformer('.//title').remove()
    <html><head/><body>Some <em>body</em> text.</body></html>

    Inserted content can be passed in the form of a string, or a Genshi event
    Stream, which includes ``genshi.builder.tag``:

    >>> from genshi.builder import tag
    >>> print html | Transformer('.//body').prepend(tag.h1('Document Title'))
    <html><head><title>Some Title</title></head><body><h1>Document
    Title</h1>Some <em>body</em> text.</body></html>

    Each XPath expression determines the set of tags that will be acted upon by
    subsequent transformations. In this example we select the <title> text, copy
    it into a buffer, then select the ``<body>`` element and paste the copied
    text into the body as ``<h1>`` enclosed text:

    >>> buffer = []
    >>> print html | Transformer('.//title/text()').copy(buffer) \\
    ...     .select('.//body').prepend(tag.h1(buffer))
    <html><head><title>Some Title</title></head><body><h1>Some Title</h1>Some
    <em>body</em> text.</body></html>

    Transformations can also be assigned and reused, although care must be
    taken when using buffers, to ensure that buffers are cleared between
    transforms:

    >>> emphasis = Transformer('.//em').setattr('class', 'emphasis')
    >>> print html | emphasis
    <html><head><title>Some Title</title></head><body>Some <em
    class="emphasis">body</em> text.</body></html>
    """

    __slots__ = ('transforms',)

    def __init__(self, path=None):
        """Construct a new transformation filter.

        :param path: the XPath expression
        """
        self.transforms = []
        if path:
            self.transforms.append(Select(path))

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        :return: the transformed stream
        :rtype: `Stream`
        """
        transforms = self._mark(stream)
        for link in self.transforms:
            transforms = link(transforms)
        return Stream(self._unmark(transforms))

    def __or__(self, function):
        """Combine transformations.

        Transformations can be chained, similar to stream filters. Any callable
        accepting a marked stream can be used as a transform.

        As an example, here is a simple `TEXT` event upper-casing transform:

        >>> def upper(stream):
        ...     for mark, (kind, data, pos) in stream:
        ...         if mark and kind is TEXT:
        ...             yield mark, (kind, data.upper(), pos)
        ...         else:
        ...             yield mark, (kind, data, pos)
        >>> short_stream = HTML('<body>Some <em>test</em> text</body>')
        >>> print short_stream | (Transformer('.//em/text()') | upper)
        <body>Some <em>TEST</em> text</body>
        """
        transform = Transformer()
        transform.transforms = self.transforms[:]
        if isinstance(function, Transformer):
            transform.transforms.extend(function.transforms)
        else:
            transform.transforms.append(function)
        return transform

    #{ Selection operations

    def select(self, path):
        """Mark events matching the given XPath expression.

        >>> html = HTML('<body>Some <em>test</em> text</body>')
        >>> print html | Transformer().select('.//em').trace()
        (None, ('START', (QName(u'body'), Attrs()), (None, 1, 0)))
        (None, ('TEXT', u'Some ', (None, 1, 6)))
        ('ENTER', ('START', (QName(u'em'), Attrs()), (None, 1, 11)))
        ('INSIDE', ('TEXT', u'test', (None, 1, 15)))
        ('EXIT', ('END', QName(u'em'), (None, 1, 19)))
        (None, ('TEXT', u' text', (None, 1, 24)))
        (None, ('END', QName(u'body'), (None, 1, 29)))
        <body>Some <em>test</em> text</body>

        :return: the stream augmented by transformation marks
        :rtype: `Transformer`
        """
        return self | Select(path)

    def invert(self):
        """Invert selection so that marked events become unmarked, and vice
        versa.

        Specificaly, all marks are converted to null marks, and all null marks
        are converted to OUTSIDE marks.

        >>> html = HTML('<body>Some <em>test</em> text</body>')
        >>> print html | Transformer('//em').invert().trace()
        ('OUTSIDE', ('START', (QName(u'body'), Attrs()), (None, 1, 0)))
        ('OUTSIDE', ('TEXT', u'Some ', (None, 1, 6)))
        (None, ('START', (QName(u'em'), Attrs()), (None, 1, 11)))
        (None, ('TEXT', u'test', (None, 1, 15)))
        (None, ('END', QName(u'em'), (None, 1, 19)))
        ('OUTSIDE', ('TEXT', u' text', (None, 1, 24)))
        ('OUTSIDE', ('END', QName(u'body'), (None, 1, 29)))
        <body>Some <em>test</em> text</body>

        :rtype: `Transformer`
        """
        return self | invert

    #{ Deletion operations

    def empty(self):
        """Empty selected elements of all content.

        Example:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').empty()
        <html><head><title>Some Title</title></head><body>Some <em/>
        text.</body></html>

        :rtype: `Transformer`
        """
        return self | empty

    def remove(self):
        """Remove selection from the stream.

        Example:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').remove()
        <html><head><title>Some Title</title></head><body>Some
        text.</body></html>

        :rtype: `Transformer`
        """
        return self | remove

    #{ Direct element operations

    def unwrap(self):
        """Remove outtermost enclosing elements from selection.

        Example:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').unwrap()
        <html><head><title>Some Title</title></head><body>Some body
        text.</body></html>

        :rtype: `Transformer`
        """
        return self | unwrap


    def wrap(self, element):
        """Wrap selection in an element.

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').wrap('strong')
        <html><head><title>Some Title</title></head><body>Some
        <strong><em>body</em></strong> text.</body></html>

        :param element: Either a string tag name or a Genshi builder element.
        :rtype: `Transformer`
        """
        return self | Wrap(element)

    #{ Content insertion operations

    def replace(self, content):
        """Replace selection with content.

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//title/text()').replace('New Title')
        <html><head><title>New Title</title></head><body>Some <em>body</em>
        text.</body></html>

        :param content: Either an iterable of events or a string to insert.
        :rtype: `Transformer`
        """
        return self | Replace(content)

    def before(self, content):
        """Insert content before selection.

        In this example we insert the word 'emphasised' before the <em> opening
        tag:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').before('emphasised ')
        <html><head><title>Some Title</title></head><body>Some emphasised
        <em>body</em> text.</body></html>

        :param content: Either an iterable of events or a string to insert.
        :rtype: `Transformer`
        """
        return self | Before(content)

    def after(self, content):
        """Insert content after selection.

        Here, we insert some text after the </em> closing tag:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').after(' rock')
        <html><head><title>Some Title</title></head><body>Some <em>body</em>
        rock text.</body></html>

        :param content: Either an iterable of events or a string to insert.
        :rtype: `Transformer`
        """
        return self | After(content)

    def prepend(self, content):
        """Insert content after the ENTER event of the selection.

        Inserting some new text at the start of the <body>:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//body').prepend('Some new body text. ')
        <html><head><title>Some Title</title></head><body>Some new body text.
        Some <em>body</em> text.</body></html>

        :param content: Either an iterable of events or a string to insert.
        :rtype: `Transformer`
        """
        return self | Prepend(content)

    def append(self, content):
        """Insert content before the END event of the selection.

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//body').append(' Some new body text.')
        <html><head><title>Some Title</title></head><body>Some <em>body</em>
        text. Some new body text.</body></html>

        :param content: Either an iterable of events or a string to insert.
        :rtype: `Transformer`
        """
        return self | Append(content)

    #{ Attribute manipulation

    def setattr(self, key, value):
        """Add or replace an attribute to selected elements.

        Example:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').setattr('class', 'emphasis')
        <html><head><title>Some Title</title></head><body>Some <em
        class="emphasis">body</em> text.</body></html>

        :rtype: `Transformer`
        """
        return self | SetAttr(key, value)

    def delattr(self, key):
        """Delete an attribute from selected elements.

        Example:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em class="emphasis">body</em> '
        ...             'text.</body></html>')
        >>> print html | Transformer('.//*[@class="emphasis"]').delattr('class')
        <html><head><title>Some Title</title></head><body>Some <em>body</em>
        text.</body></html>

        :rtype: `Transformer`
        """
        return self | DelAttr(key)

    #{ Buffer operations

    def copy(self, buffer):
        """Copy selection into buffer.

        >>> from genshi.builder import tag
        >>> buffer = []
        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//title/text()').copy(buffer) \\
        ...     .select('.//body').prepend(tag.h1(buffer))
        <html><head><title>Some Title</title></head><body><h1>Some Title</h1>Some
        <em>body</em> text.</body></html>

        :param buffer: a list-like object (must support .append() and be
                       iterable) where the selection will be buffered.
        :rtype: `Transformer`
        :note: this transformation will buffer the entire input stream
        """
        return self | Copy(buffer)

    def cut(self, buffer):
        """Copy selection into buffer and remove the selection from the stream.

        >>> from genshi.builder import tag
        >>> buffer = []
        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em/text()').cut(buffer) \\
        ...     .select('.//em').after(tag.h1(buffer))
        <html><head><title>Some Title</title></head><body>Some
        <em/><h1>body</h1> text.</body></html>

        :param buffer: a list-like object (must support .append() and be
                       iterable) where the selection will be buffered.
        :rtype: `Transformer`
        :note: this transformation will buffer the entire input stream
        """
        return self | Cut(buffer)

    #{ Miscellaneous operations

    def apply(self, function, kind):
        """Apply a function to the ``data`` element of events of ``kind`` in
        the selection.

        >>> import string
        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...               '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('head/title').apply(string.upper, TEXT)
        <html><head><title>SOME TITLE</title></head><body>Some <em>body</em>
        text.</body></html>

        :param function: the function to apply
        :param kind: the kind of event the function should be applied to
        :rtype: `Transformer`
        """
        return self | Apply(function, kind)

    def trace(self, prefix='', fileobj=None):
        """Print events as they pass through the transform.

        >>> html = HTML('<body>Some <em>test</em> text</body>')
        >>> print html | Transformer('em').trace()
        (None, ('START', (QName(u'body'), Attrs()), (None, 1, 0)))
        (None, ('TEXT', u'Some ', (None, 1, 6)))
        ('ENTER', ('START', (QName(u'em'), Attrs()), (None, 1, 11)))
        ('INSIDE', ('TEXT', u'test', (None, 1, 15)))
        ('EXIT', ('END', QName(u'em'), (None, 1, 19)))
        (None, ('TEXT', u' text', (None, 1, 24)))
        (None, ('END', QName(u'body'), (None, 1, 29)))
        <body>Some <em>test</em> text</body>

        :param prefix: a string to prefix each event with in the output
        :param fileobj: the writable file-like object to write to; defaults to
                        the standard output stream
        :rtype: `Transformer`
        """
        return self | Trace(prefix, fileobj=fileobj)

    # Internal methods

    def _mark(self, stream):
        for event in stream:
            yield None, event

    def _unmark(self, stream):
        for mark, event in stream:
            yield event


class Select(object):
    """Select and mark events that match an XPath expression."""
    def __init__(self, path):
        """Create selection.

        :param path: XPath expression.
        """
        self.path = Path(path)

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        namespaces = {}
        variables = {}
        test = self.path.test()
        stream = iter(stream)
        for mark, event in stream:
            result = test(event, {}, {})
            if result is True:
                if event[0] is START:
                    yield ENTER, event
                    depth = 1
                    while depth > 0:
                        mark, subevent = stream.next()
                        if subevent[0] is START:
                            depth += 1
                        elif subevent[0] is END:
                            depth -= 1
                        if depth == 0:
                            yield EXIT, subevent
                        else:
                            yield INSIDE, subevent
                        test(subevent, {}, {}, updateonly=True)
                else:
                    yield OUTSIDE, event
            elif result:
                yield ENTER, result
            else:
                yield None, event


def invert(stream):
    """Invert selection so that marked events become unmarked, and vice versa.

    Specificaly, all input marks are converted to null marks, and all input
    null marks are converted to OUTSIDE marks.

    :param stream: The marked event stream to filter
    """
    for mark, event in stream:
        if mark:
            yield None, event
        else:
            yield OUTSIDE, event

def empty(stream):
    """Empty selected elements of all content.

    :param stream: The marked event stream to filter
    """
    for mark, event in stream:
        if mark not in (INSIDE, OUTSIDE):
            yield mark, event

def remove(stream):
    """Remove selection from the stream.

    :param stream: The marked event stream to filter
    """
    for mark, event in stream:
        if mark is None:
            yield mark, event

def unwrap(stream):
    """Remove outtermost enclosing elements from selection.

    :param stream: The marked event stream to filter
    """
    for mark, event in stream:
        if mark not in (ENTER, EXIT):
            yield mark, event


class Wrap(object):
    """Wrap selection in an element."""

    def __init__(self, element):
        if isinstance(element, Element):
            self.element = element
        else:
            self.element = Element(element)

    def __call__(self, stream):
        for mark, event in stream:
            if mark:
                element = list(self.element.generate())
                for prefix in element[:-1]:
                    yield None, prefix
                yield mark, event
                while True:
                    mark, event = stream.next()
                    if not mark:
                        break
                    yield mark, event
                yield None, element[-1]
                yield mark, event
            else:
                yield mark, event


class Trace(object):
    """Print events as they pass through the transform."""

    def __init__(self, prefix='', fileobj=None):
        """Trace constructor.

        :param prefix: text to prefix each traced line with.
        :param fileobj: the writable file-like object to write to
        """
        self.prefix = prefix
        self.fileobj = fileobj or sys.stdout

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for event in stream:
            print>>self.fileobj, self.prefix + str(event)
            yield event


class Apply(object):
    """Apply a function to the `data` element of events of ``kind`` in the
    selection.
    """

    def __init__(self, function, kind):
        """Create the transform.

        :param function: The function to apply. The function must take one
                         argument, the `data` element of each selected event.
        :param kind: The Genshi event `kind` to apply ``function`` to.
        """
        self.function = function
        self.kind = kind

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, (kind, data, pos) in stream:
            if mark and kind == self.kind:
                yield mark, (kind, self.function(data), pos)
            else:
                yield mark, (kind, data, pos)


class Injector(object):
    """Abstract base class for transformations that inject content into a
    stream.

    >>> class Top(Injector):
    ...     def __call__(self, stream):
    ...         for event in self._inject():
    ...             yield event
    ...         for event in stream:
    ...             yield event
    >>> html = HTML('<body>Some <em>test</em> text</body>')
    >>> print html | (Transformer('.//em') | Top('Prefix '))
    Prefix <body>Some <em>test</em> text</body>
    """
    def __init__(self, content):
        """Create a new injector.

        :param content: An iterable of Genshi stream events, or a string to be
                        injected.
        """
        self.content = content

    def _inject(self):
        if isinstance(self.content, basestring):
            yield None, (TEXT, self.content, (None, -1, -1))
        else:
            for event in self.content:
                yield None, event


class Replace(Injector):
    """Replace selection with content."""
    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, event in stream:
            if mark is not None:
                for subevent in self._inject():
                    yield subevent
                while True:
                    mark, event = stream.next()
                    if mark is None:
                        yield mark, event
                        break
            else:
                yield mark, event


class Before(Injector):
    """Insert content before selection."""
    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, event in stream:
            if mark in (ENTER, OUTSIDE):
                for subevent in self._inject():
                    yield subevent
            yield mark, event


class After(Injector):
    """Insert content after selection."""
    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, event in stream:
            yield mark, event
            if mark:
                while True:
                    mark, event = stream.next()
                    if not mark:
                        break
                    yield mark, event
                for subevent in self._inject():
                    yield subevent
                yield mark, event


class Prepend(Injector):
    """Prepend content to the inside of selected elements."""
    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, event in stream:
            yield mark, event
            if mark in (ENTER, OUTSIDE):
                for subevent in self._inject():
                    yield subevent


class Append(Injector):
    """Append content after the content of selected elements."""
    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, event in stream:
            yield mark, event
            if mark is ENTER:
                while True:
                    mark, event = stream.next()
                    if mark is EXIT:
                        break
                    yield mark, event
                for subevent in self._inject():
                    yield subevent
                yield mark, event


class SetAttr(object):
    """Set an attribute on selected elements."""
    def __init__(self, key, value):
        """Construct transform.

        :param key: Attribute to set.
        :param value: Value of attribute.
        """
        self.key = key
        self.value = value

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, (kind, data, pos) in stream:
            if mark is ENTER:
                data = (data[0], data[1] | [(QName(self.key), self.value)])
            yield mark, (kind, data, pos)


class DelAttr(object):
    """Delete an attribute of selected elements."""
    def __init__(self, key):
        """Construct transform.

        :param key: The attribute to remove."""
        self.key = key

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, (kind, data, pos) in stream:
            if mark is ENTER:
                data = (data[0], data[1] - self.key)
            yield mark, (kind, data, pos)


class Copy(object):
    """Copy selected events into a buffer for later insertion."""
    def __init__(self, buffer):
        """Create a Copy transform filter.

        :param buffer: A list-like object (must support .append() and be
                       iterable) where the buffered events will be stored.
        """
        self.buffer = buffer

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        stream = list(stream)
        for mark, event in stream:
            if mark:
                self.buffer.append(event)
        return stream


class Cut(Copy):
    """Cut selected events into a buffer for later insertion and remove the
    selection."""
    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        stream = Copy.__call__(self, stream)
        return remove(stream)


if __name__ == '__main__':
    import doctest
    from genshi.input import HTML
    doctest.testmod(optionflags=doctest.NORMALIZE_WHITESPACE,
                    extraglobs={'HTML': HTML})
