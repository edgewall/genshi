# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""A filter for functional-style transformations of markup streams.

The `Transformer` filter provides a variety of transformations that can be
applied to parts of streams that match given XPath expressions. These
transformations can be chained to achieve results that would be comparitively
tedious to achieve by writing stream filters by hand. The approach of chaining
node selection and transformation has been inspired by the `jQuery`_ Javascript
library.

 .. _`jQuery`: http://jquery.com/

For example, the following transformation removes the ``<title>`` element from
the ``<head>`` of the input document:

>>> from genshi.builder import tag
>>> html = HTML('''<html>
...  <head><title>Some Title</title></head>
...  <body>
...    Some <em>body</em> text.
...  </body>
... </html>''')
>>> print html | Transformer('body/em').map(unicode.upper, TEXT) \\
...                                    .unwrap().wrap(tag.u)
<html>
  <head><title>Some Title</title></head>
  <body>
    Some <u>BODY</u> text.
  </body>
</html>

The ``Transformer`` support a large number of useful transformations out of the
box, but custom transformations can be added easily.

:since: version 0.5
"""

import re
import sys

from genshi.builder import Element
from genshi.core import Stream, Attrs, QName, TEXT, START, END, _ensure, Markup
from genshi.path import Path

__all__ = ['Transformer', 'StreamBuffer', 'InjectorTransformation', 'ENTER',
           'EXIT', 'INSIDE', 'OUTSIDE']


class TransformMark(str):
    """A mark on a transformation stream."""
    __slots__ = []
    _instances = {}

    def __new__(cls, val):
        return cls._instances.setdefault(val, str.__new__(cls, val))


ENTER = TransformMark('ENTER')
"""Stream augmentation mark indicating that a selected element is being
entered."""

INSIDE = TransformMark('INSIDE')
"""Stream augmentation mark indicating that processing is currently inside a
selected element."""

OUTSIDE = TransformMark('OUTSIDE')
"""Stream augmentation mark indicating that a match occurred outside a selected
element."""

ATTR = TransformMark('ATTR')
"""Stream augmentation mark indicating a selected element attribute."""

EXIT = TransformMark('EXIT')
"""Stream augmentation mark indicating that a selected element is being
exited."""


class Transformer(object):
    """Stream filter that can apply a variety of different transformations to
    a stream.

    This is achieved by selecting the events to be transformed using XPath,
    then applying the transformations to the events matched by the path
    expression. Each marked event is in the form (mark, (kind, data, pos)),
    where mark can be any of `ENTER`, `INSIDE`, `EXIT`, `OUTSIDE`, or `None`.

    The first three marks match `START` and `END` events, and any events
    contained `INSIDE` any selected XML/HTML element. A non-element match
    outside a `START`/`END` container (e.g. ``text()``) will yield an `OUTSIDE`
    mark.

    >>> html = HTML('<html><head><title>Some Title</title></head>'
    ...             '<body>Some <em>body</em> text.</body></html>')

    Transformations act on selected stream events matching an XPath expression.
    Here's an example of removing some markup (the title, in this case)
    selected by an expression:

    >>> print html | Transformer('head/title').remove()
    <html><head/><body>Some <em>body</em> text.</body></html>

    Inserted content can be passed in the form of a string, or a markup event
    stream, which includes streams generated programmatically via the
    `builder` module:

    >>> from genshi.builder import tag
    >>> print html | Transformer('body').prepend(tag.h1('Document Title'))
    <html><head><title>Some Title</title></head><body><h1>Document
    Title</h1>Some <em>body</em> text.</body></html>

    Each XPath expression determines the set of tags that will be acted upon by
    subsequent transformations. In this example we select the ``<title>`` text,
    copy it into a buffer, then select the ``<body>`` element and paste the
    copied text into the body as ``<h1>`` enclosed text:

    >>> buffer = StreamBuffer()
    >>> print html | Transformer('head/title/text()').copy(buffer) \\
    ...     .end().select('body').prepend(tag.h1(buffer))
    <html><head><title>Some Title</title></head><body><h1>Some Title</h1>Some
    <em>body</em> text.</body></html>

    Transformations can also be assigned and reused, although care must be
    taken when using buffers, to ensure that buffers are cleared between
    transforms:

    >>> emphasis = Transformer('body//em').attr('class', 'emphasis')
    >>> print html | emphasis
    <html><head><title>Some Title</title></head><body>Some <em
    class="emphasis">body</em> text.</body></html>
    """

    __slots__ = ['transforms']

    def __init__(self, path=None):
        """Construct a new transformation filter.

        :param path: an XPath expression (as string) or a `Path` instance
        """
        if path is not None:
            self.transforms = [SelectTransformation(path)]
        else:
            self.transforms = []

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: the marked event stream to filter
        :return: the transformed stream
        :rtype: `Stream`
        """
        transforms = self._mark(stream)
        for link in self.transforms:
            transforms = link(transforms)
        return Stream(self._unmark(transforms),
                      serializer=getattr(stream, 'serializer', None))

    def apply(self, function):
        """Apply a transformation to the stream.

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
        >>> print short_stream | Transformer('.//em/text()').apply(upper)
        <body>Some <em>TEST</em> text</body>
        """
        transformer = Transformer()
        transformer.transforms = self.transforms[:]
        if isinstance(function, Transformer):
            transformer.transforms.extend(function.transforms)
        else:
            transformer.transforms.append(function)
        return transformer

    #{ Selection operations

    def select(self, path):
        """Mark events matching the given XPath expression, within the current
        selection.

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

        :param path: an XPath expression (as string) or a `Path` instance
        :return: the stream augmented by transformation marks
        :rtype: `Transformer`
        """
        return self.apply(SelectTransformation(path))

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
        return self.apply(InvertTransformation())

    def end(self):
        """End current selection, allowing all events to be selected.

        Example:

        >>> html = HTML('<body>Some <em>test</em> text</body>')
        >>> print html | Transformer('//em').end().trace()
        ('OUTSIDE', ('START', (QName(u'body'), Attrs()), (None, 1, 0)))
        ('OUTSIDE', ('TEXT', u'Some ', (None, 1, 6)))
        ('OUTSIDE', ('START', (QName(u'em'), Attrs()), (None, 1, 11)))
        ('OUTSIDE', ('TEXT', u'test', (None, 1, 15)))
        ('OUTSIDE', ('END', QName(u'em'), (None, 1, 19)))
        ('OUTSIDE', ('TEXT', u' text', (None, 1, 24)))
        ('OUTSIDE', ('END', QName(u'body'), (None, 1, 29)))
        <body>Some <em>test</em> text</body>

        :return: the stream augmented by transformation marks
        :rtype: `Transformer`
        """
        return self.apply(EndTransformation())

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
        return self.apply(EmptyTransformation())

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
        return self.apply(RemoveTransformation())

    #{ Direct element operations

    def unwrap(self):
        """Remove outermost enclosing elements from selection.

        Example:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').unwrap()
        <html><head><title>Some Title</title></head><body>Some body
        text.</body></html>

        :rtype: `Transformer`
        """
        return self.apply(UnwrapTransformation())

    def wrap(self, element):
        """Wrap selection in an element.

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em').wrap('strong')
        <html><head><title>Some Title</title></head><body>Some
        <strong><em>body</em></strong> text.</body></html>

        :param element: either a tag name (as string) or an `Element` object
        :rtype: `Transformer`
        """
        return self.apply(WrapTransformation(element))

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
        return self.apply(ReplaceTransformation(content))

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
        return self.apply(BeforeTransformation(content))

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
        return self.apply(AfterTransformation(content))

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
        return self.apply(PrependTransformation(content))

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
        return self.apply(AppendTransformation(content))

    #{ Attribute manipulation

    def attr(self, name, value):
        """Add, replace or delete an attribute on selected elements.

        If `value` evaulates to `None` the attribute will be deleted from the
        element:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em class="before">body</em> <em>text</em>.</body>'
        ...             '</html>')
        >>> print html | Transformer('body/em').attr('class', None)
        <html><head><title>Some Title</title></head><body>Some <em>body</em>
        <em>text</em>.</body></html>

        Otherwise the attribute will be set to `value`:

        >>> print html | Transformer('body/em').attr('class', 'emphasis')
        <html><head><title>Some Title</title></head><body>Some <em
        class="emphasis">body</em> <em class="emphasis">text</em>.</body></html>

        If `value` is a callable it will be called with the attribute name and
        the `START` event for the matching element. Its return value will then
        be used to set the attribute:

        >>> def print_attr(name, event):
        ...     attrs = event[1][1]
        ...     print attrs
        ...     return attrs.get(name)
        >>> print html | Transformer('body/em').attr('class', print_attr)
        Attrs([(QName(u'class'), u'before')])
        Attrs()
        <html><head><title>Some Title</title></head><body>Some <em
        class="before">body</em> <em>text</em>.</body></html>

        :param name: the name of the attribute
        :param value: the value that should be set for the attribute.
        :rtype: `Transformer`
        """
        return self.apply(AttrTransformation(name, value))

    #{ Buffer operations

    def copy(self, buffer):
        """Copy selection into buffer.

        >>> from genshi.builder import tag
        >>> buffer = StreamBuffer()
        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('title/text()').copy(buffer) \\
        ...     .end().select('body').prepend(tag.h1(buffer))
        <html><head><title>Some Title</title></head><body><h1>Some
        Title</h1>Some <em>body</em> text.</body></html>

        To ensure that a transformation can be reused deterministically, the
        contents of ``buffer`` is replaced by the ``copy()`` operation:

        >>> print buffer
        Some Title
        >>> print html | Transformer('head/title/text()').copy(buffer) \\
        ...     .end().select('body/em').copy(buffer).end().select('body') \\
        ...     .prepend(tag.h1(buffer))
        <html><head><title>Some
        Title</title></head><body><h1><em>body</em></h1>Some <em>body</em>
        text.</body></html>
        >>> print buffer
        <em>body</em>

        Element attributes can also be copied for later use:

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body><em>Some</em> <em class="before">body</em>'
        ...             '<em>text</em>.</body></html>')
        >>> buffer = StreamBuffer()
        >>> def apply_attr(name, entry):
        ...     return list(buffer)[0][1][1].get('class')
        >>> print html | Transformer('body/em[@class]/@class').copy(buffer) \\
        ...     .end().select('body/em[not(@class)]').attr('class', apply_attr)
        <html><head><title>Some Title</title></head><body><em
        class="before">Some</em> <em class="before">body</em><em
        class="before">text</em>.</body></html>


        :param buffer: the `StreamBuffer` in which the selection should be
                       stored
        :rtype: `Transformer`
        :note: this transformation will buffer the entire input stream
        """
        return self.apply(CopyTransformation(buffer))

    def cut(self, buffer):
        """Copy selection into buffer and remove the selection from the stream.

        >>> from genshi.builder import tag
        >>> buffer = StreamBuffer()
        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...             '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('.//em/text()').cut(buffer) \\
        ...     .end().select('.//em').after(tag.h1(buffer))
        <html><head><title>Some Title</title></head><body>Some
        <em/><h1>body</h1> text.</body></html>

        :param buffer: the `StreamBuffer` in which the selection should be
                       stored
        :rtype: `Transformer`
        :note: this transformation will buffer the entire input stream
        """
        return self.apply(CutTransformation(buffer))

    #{ Miscellaneous operations

    def filter(self, filter):
        """Apply a normal stream filter to the selection. The filter is called
        once for each contiguous block of marked events.

        >>> from genshi.filters.html import HTMLSanitizer
        >>> html = HTML('<html><body>Some text<script>alert(document.cookie)'
        ...             '</script> and some more text</body></html>')
        >>> print html | Transformer('body/*').filter(HTMLSanitizer())
        <html><body>Some text and some more text</body></html>

        :param filter: The stream filter to apply.
        :rtype: `Transformer`
        """
        return self.apply(FilterTransformation(filter))

    def map(self, function, kind):
        """Applies a function to the ``data`` element of events of ``kind`` in
        the selection.

        >>> html = HTML('<html><head><title>Some Title</title></head>'
        ...               '<body>Some <em>body</em> text.</body></html>')
        >>> print html | Transformer('head/title').map(unicode.upper, TEXT)
        <html><head><title>SOME TITLE</title></head><body>Some <em>body</em>
        text.</body></html>

        :param function: the function to apply
        :param kind: the kind of event the function should be applied to
        :rtype: `Transformer`
        """
        return self.apply(MapTransformation(function, kind))

    def substitute(self, pattern, replace, count=1):
        """Replace text matching a regular expression.

        Refer to the documentation for ``re.sub()`` for details.

        >>> html = HTML('<html><body>Some text, some more text and '
        ...             '<b>some bold text</b></body></html>')
        >>> print html | Transformer('body').substitute('(?i)some', 'SOME')
        <html><body>SOME text, some more text and <b>SOME bold text</b></body></html>
        >>> tags = tag.html(tag.body('Some text, some more text and ',
        ...      Markup('<b>some bold text</b>')))
        >>> print tags.generate() | Transformer('body').substitute('(?i)some', 'SOME')
        <html><body>SOME text, some more text and <b>SOME bold text</b></body></html>

        :param pattern: A regular expression object or string.
        :param replace: Replacement pattern.
        :param count: Number of replacements to make in each text fragment.
        :rtype: `Transformer`
        """
        return self.apply(SubstituteTransformation(pattern, replace, count))

    def rename(self, name):
        """Rename matching elements.

        >>> html = HTML('<html><body>Some text, some more text and '
        ...             '<b>some bold text</b></body></html>')
        >>> print html | Transformer('body/b').rename('strong')
        <html><body>Some text, some more text and <strong>some bold text</strong></body></html>
        """
        return self.apply(RenameTransformation(name))

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
        return self.apply(TraceTransformation(prefix, fileobj=fileobj))

    # Internal methods

    def _mark(self, stream):
        for event in stream:
            yield OUTSIDE, event

    def _unmark(self, stream):
        for mark, event in stream:
            if event[0] is not None:
                yield event


class SelectTransformation(object):
    """Select and mark events that match an XPath expression."""

    def __init__(self, path):
        """Create selection.

        :param path: an XPath expression (as string) or a `Path` object
        """
        if not isinstance(path, Path):
            path = Path(path)
        self.path = path

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: the marked event stream to filter
        """
        namespaces = {}
        variables = {}
        test = self.path.test()
        stream = iter(stream)
        for mark, event in stream:
            if mark is None:
                yield mark, event
                continue
            result = test(event, {}, {})
            # XXX This is effectively genshi.core._ensure() for transform
            # streams.
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
            elif isinstance(result, Attrs):
                # XXX  Selected *attributes* are given a "kind" of None to
                # indicate they are not really part of the stream.
                yield ATTR, (None, (QName(event[1][0] + '@*'), result), event[2])
                yield None, event
            elif isinstance(result, tuple):
                print result
                yield None, result
            elif result:
                yield None, (TEXT, unicode(result), (None, -1, -1))
            else:
                yield None, event


class InvertTransformation(object):
    """Invert selection so that marked events become unmarked, and vice versa.

    Specificaly, all input marks are converted to null marks, and all input
    null marks are converted to OUTSIDE marks.
    """

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: the marked event stream to filter
        """
        for mark, event in stream:
            if mark:
                yield None, event
            else:
                yield OUTSIDE, event


class EndTransformation(object):
    """End the current selection."""

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: the marked event stream to filter
        """
        for mark, event in stream:
            yield OUTSIDE, event


class EmptyTransformation(object):
    """Empty selected elements of all content."""

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: the marked event stream to filter
        """
        for mark, event in stream:
            if mark not in (INSIDE, OUTSIDE):
                yield mark, event


class RemoveTransformation(object):
    """Remove selection from the stream."""

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: the marked event stream to filter
        """
        for mark, event in stream:
            if mark is None:
                yield mark, event


class UnwrapTransformation(object):
    """Remove outtermost enclosing elements from selection."""

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: the marked event stream to filter
        """
        for mark, event in stream:
            if mark not in (ENTER, EXIT):
                yield mark, event


class WrapTransformation(object):
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
                    try:
                        mark, event = stream.next()
                    except StopIteration:
                        yield None, element[-1]
                    if not mark:
                        break
                    yield mark, event
                yield None, element[-1]
                yield mark, event
            else:
                yield mark, event


class TraceTransformation(object):
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

        :param stream: the marked event stream to filter
        """
        for event in stream:
            print>>self.fileobj, self.prefix + str(event)
            yield event


class FilterTransformation(object):
    """Apply a normal stream filter to the selection. The filter is called once
    for each contiguous block of marked events."""

    def __init__(self, filter):
        """Create the transform.

        :param filter: The stream filter to apply.
        """
        self.filter = filter

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        def flush(queue):
            if queue:
                for event in self.filter(queue):
                    yield OUTSIDE, event
                del queue[:]

        queue = []
        for mark, event in stream:
            if mark:
                queue.append(event)
            else:
                for queue_event in flush(queue):
                    yield queue_event
                yield None, event
        for event in flush(queue):
            yield event


class MapTransformation(object):
    """Apply a function to the `data` element of events of ``kind`` in the
    selection.
    """

    def __init__(self, function, kind):
        """Create the transform.

        :param function: the function to apply; the function must take one
                         argument, the `data` element of each selected event
        :param kind: the stream event ``kind`` to apply the `function` to
        """
        self.function = function
        self.kind = kind

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, (kind, data, pos) in stream:
            if mark and self.kind in (None, kind):
                yield mark, (kind, self.function(data), pos)
            else:
                yield mark, (kind, data, pos)


class SubstituteTransformation(object):
    """Replace text matching a regular expression.

    Refer to the documentation for ``re.sub()`` for details.
    """
    def __init__(self, pattern, replace, count=1):
        """Create the transform.

        :param pattern: A regular expression object, or string.
        :param replace: Replacement pattern.
        :param count: Number of replacements to make in each text fragment.
        """
        if isinstance(pattern, basestring):
            self.pattern = re.compile(pattern)
        else:
            self.pattern = pattern
        self.count = count
        self.replace = replace

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, (kind, data, pos) in stream:
            if kind is TEXT:
                new_data = self.pattern.sub(self.replace, data, self.count)
                if isinstance(data, Markup):
                    data = Markup(new_data)
                else:
                    data = new_data
            yield mark, (kind, data, pos)


class RenameTransformation(object):
    """Rename matching elements."""
    def __init__(self, name):
        """Create the transform.

        :param name: New element name.
        """
        self.name = QName(name)

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, (kind, data, pos) in stream:
            if mark is ENTER:
                data = self.name, data[1]
            elif mark is EXIT:
                data = self.name
            yield mark, (kind, data, pos)


class InjectorTransformation(object):
    """Abstract base class for transformations that inject content into a
    stream.

    >>> class Top(InjectorTransformation):
    ...     def __call__(self, stream):
    ...         for event in self._inject():
    ...             yield event
    ...         for event in stream:
    ...             yield event
    >>> html = HTML('<body>Some <em>test</em> text</body>')
    >>> print html | Transformer('.//em').apply(Top('Prefix '))
    Prefix <body>Some <em>test</em> text</body>
    """
    def __init__(self, content):
        """Create a new injector.

        :param content: An iterable of Genshi stream events, or a string to be
                        injected.
        """
        self.content = content

    def _inject(self):
        for event in _ensure(self.content):
            yield None, event


class ReplaceTransformation(InjectorTransformation):
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


class BeforeTransformation(InjectorTransformation):
    """Insert content before selection."""

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, event in stream:
            if mark is not None:
                for subevent in self._inject():
                    yield subevent
                yield mark, event
                while True:
                    mark, event = stream.next()
                    if not mark:
                        break
                    yield mark, event
            yield mark, event


class AfterTransformation(InjectorTransformation):
    """Insert content after selection."""

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        for mark, event in stream:
            yield mark, event
            if mark:
                while True:
                    try:
                        mark, event = stream.next()
                    except StopIteration:
                        break
                    if not mark:
                        break
                    yield mark, event
                for subevent in self._inject():
                    yield subevent
                yield mark, event


class PrependTransformation(InjectorTransformation):
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


class AppendTransformation(InjectorTransformation):
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


class AttrTransformation(object):
    """Set an attribute on selected elements."""

    def __init__(self, name, value):
        """Construct transform.

        :param name: name of the attribute that should be set
        :param value: the value to set
        """
        self.name = name
        self.value = value

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: The marked event stream to filter
        """
        callable_value = callable(self.value)
        for mark, (kind, data, pos) in stream:
            if mark is ENTER:
                if callable_value:
                    value = self.value(self.name, (kind, data, pos))
                else:
                    value = self.value
                if value is None:
                    attrs = data[1] - [QName(self.name)]
                else:
                    attrs = data[1] | [(QName(self.name), value)]
                data = (data[0], attrs)
            yield mark, (kind, data, pos)



class StreamBuffer(Stream):
    """Stream event buffer used for cut and copy transformations."""

    def __init__(self):
        """Create the buffer."""
        Stream.__init__(self, [])

    def append(self, event):
        """Add an event to the buffer.

        :param event: the markup event to add
        """
        self.events.append(event)

    def reset(self):
        """Reset the buffer so that it's empty."""
        del self.events[:]


class CopyTransformation(object):
    """Copy selected events into a buffer for later insertion."""

    def __init__(self, buffer):
        """Create the copy transformation.

        :param buffer: the `StreamBuffer` in which the selection should be
                       stored
        """
        self.buffer = buffer

    def __call__(self, stream):
        """Apply the transformation to the marked stream.

        :param stream: the marked event stream to filter
        """
        self.buffer.reset()
        stream = list(stream)
        for mark, event in stream:
            if mark:
                self.buffer.append(event)
        return stream


class CutTransformation(object):
    """Cut selected events into a buffer for later insertion and remove the
    selection.
    """

    def __init__(self, buffer):
        """Create the cut transformation.

        :param buffer: the `StreamBuffer` in which the selection should be
                       stored
        """
        self.buffer = buffer

    def __call__(self, stream):
        """Apply the transform filter to the marked stream.

        :param stream: the marked event stream to filter
        """
        out_stream = []
        attributes = None
        for mark, (kind, data, pos) in stream:
            if attributes:
                assert kind is START
                data = (data[0], data[1] - attributes)
                attributes = None
            if mark:
                # There is some magic here. ATTR marked events are pushed into
                # the stream *before* the START event they originated from.
                # This allows cut() to strip out the attributes from START
                # event as would be expected.
                if mark is ATTR:
                    self.buffer.append((kind, data, pos))
                    attributes = [name for name, _ in data[1]]
                else:
                    self.buffer.append((kind, data, pos))
            else:
                out_stream.append((mark, (kind, data, pos)))
        return out_stream
