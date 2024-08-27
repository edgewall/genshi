.. -*- mode: rst; encoding: utf-8 -*-

==============
Markup Streams
==============

A stream is the common representation of markup as a *stream of events*.


Basics
======

A stream can be attained in a number of ways. It can be:

* the result of parsing XML or HTML text, or
* the result of selecting a subset of another stream using XPath, or
* programmatically generated.

For example, the functions ``XML()`` and ``HTML()`` can be used to convert
literal XML or HTML text to a markup stream:

.. code-block:: pycon

  >>> from genshi import XML
  >>> stream = XML('<p class="intro">Some text and '
  ...              '<a href="http://example.org/">a link</a>.'
  ...              '<br/></p>')
  >>> stream
  <genshi.core.Stream object at ...>

The stream is the result of parsing the text into events. Each event is a tuple
of the form ``(kind, data, pos)``, where:

* ``kind`` defines what kind of event it is (such as the start of an element,
  text, a comment, etc).
* ``data`` is the actual data associated with the event. How this looks depends
  on the event kind (see  `event kinds`_)
* ``pos`` is a ``(filename, lineno, column)`` tuple that describes where the
  event “comes from”.

.. code-block:: pycon

  >>> for kind, data, pos in stream:
  ...     print('%s %r %r' % (kind, data, pos))
  ... 
  START (QName('p'), Attrs([(QName('class'), u'intro')])) (None, 1, 0)
  TEXT u'Some text and ' (None, 1, 17)
  START (QName('a'), Attrs([(QName('href'), u'http://example.org/')])) (None, 1, 31)
  TEXT u'a link' (None, 1, 61)
  END QName('a') (None, 1, 67)
  TEXT u'.' (None, 1, 71)
  START (QName('br'), Attrs()) (None, 1, 72)
  END QName('br') (None, 1, 77)
  END QName('p') (None, 1, 77)


Filtering
=========

One important feature of markup streams is that you can apply *filters* to the
stream, either filters that come with Genshi, or your own custom filters.

A filter is simply a callable that accepts the stream as parameter, and returns
the filtered stream:

.. code-block:: python

  def noop(stream):
      """A filter that doesn't actually do anything with the stream."""
      for kind, data, pos in stream:
          yield kind, data, pos

Filters can be applied in a number of ways. The simplest is to just call the
filter directly:

.. code-block:: python

  stream = noop(stream)

The ``Stream`` class also provides a ``filter()`` method, which takes an
arbitrary number of filter callables and applies them all:

.. code-block:: python

  stream = stream.filter(noop)

Finally, filters can also be applied using the *bitwise or* operator (``|``),
which allows a syntax similar to pipes on Unix shells:

.. code-block:: python

  stream = stream | noop

One example of a filter included with Genshi is the ``HTMLSanitizer`` in
``genshi.filters``. It processes a stream of HTML markup, and strips out any
potentially dangerous constructs, such as Javascript event handlers.
``HTMLSanitizer`` is not a function, but rather a class that implements
``__call__``, which means instances of the class are callable:

.. code-block:: python

  stream = stream | HTMLSanitizer()

Both the ``filter()`` method and the pipe operator allow easy chaining of
filters:

.. code-block:: python

  from genshi.filters import HTMLSanitizer
  stream = stream.filter(noop, HTMLSanitizer())

That is equivalent to:

.. code-block:: python

  stream = stream | noop | HTMLSanitizer()

For more information about the built-in filters, see `Stream Filters`_.

.. _`Stream Filters`: filters.html


Serialization
=============

Serialization means producing some kind of textual output from a stream of
events, which you'll need when you want to transmit or store the results of
generating or otherwise processing markup.

The ``Stream`` class provides two methods for serialization: ``serialize()``
and ``render()``. The former is a generator that yields chunks of ``Markup``
objects (which are basically unicode strings that are considered safe for
output on the web). The latter returns a single string, by default UTF-8
encoded.

Here's the output from ``serialize()``:

.. code-block:: pycon

  >>> for output in stream.serialize():
  ...     print(repr(output))
  ... 
  <Markup u'<p class="intro">'>
  <Markup u'Some text and '>
  <Markup u'<a href="http://example.org/">'>
  <Markup u'a link'>
  <Markup u'</a>'>
  <Markup u'.'>
  <Markup u'<br/>'>
  <Markup u'</p>'>

And here's the output from ``render()``:

.. code-block:: pycon

  >>> print(stream.render())
  <p class="intro">Some text and <a href="http://example.org/">a link</a>.<br/></p>

Both methods can be passed a ``method`` parameter that determines how exactly
the events are serialized to text. This parameter can be either a string or a 
custom serializer class:

.. code-block:: pycon

  >>> print(stream.render('html'))
  <p class="intro">Some text and <a href="http://example.org/">a link</a>.<br></p>

Note how the `<br>` element isn't closed, which is the right thing to do for
HTML. See  `serialization methods`_ for more details.

In addition, the ``render()`` method takes an ``encoding`` parameter, which
defaults to “UTF-8”. If set to ``None``, the result will be a unicode string.

The different serializer classes in ``genshi.output`` can also be used
directly:

.. code-block:: pycon

  >>> from genshi.filters import HTMLSanitizer
  >>> from genshi.output import TextSerializer
  >>> print(''.join(TextSerializer()(HTMLSanitizer()(stream))))
  Some text and a link.

The pipe operator allows a nicer syntax:

.. code-block:: pycon

  >>> print(stream | HTMLSanitizer() | TextSerializer())
  Some text and a link.


.. _`serialization methods`:

Serialization Methods
---------------------

Genshi supports the use of different serialization methods to use for creating
a text representation of a markup stream.

``xml``
  The ``XMLSerializer`` is the default serialization method and results in
  proper XML output including namespace support, the XML declaration, CDATA
  sections, and so on. It is not generally not suitable for serving HTML or
  XHTML web pages (unless you want to use true XHTML 1.1), for which the
  ``xhtml`` and ``html`` serializers described below should be preferred.

``xhtml``
  The ``XHTMLSerializer`` is a specialization of the generic ``XMLSerializer``
  that understands the pecularities of producing XML-compliant output that can
  also be parsed without problems by the HTML parsers found in modern web
  browsers. Thus, the output by this serializer should be usable whether sent
  as "text/html" or "application/xhtml+html" (although there are a lot of
  subtle issues to pay attention to when switching between the two, in
  particular with respect to differences in the DOM and CSS).

  For example, instead of rendering a script tag as ``<script/>`` (which
  confuses the HTML parser in many browsers), it will produce
  ``<script></script>``. Also, it will normalize any boolean attributes values
  that are minimized in HTML, so that for example ``<hr noshade="1"/>``
  becomes ``<hr noshade="noshade" />``.

  This serializer supports the use of namespaces for compound documents, for
  example to use inline SVG inside an XHTML document.

``html``
  The ``HTMLSerializer`` produces proper HTML markup. The main differences
  compared to ``xhtml`` serialization are that boolean attributes are
  minimized, empty tags are not self-closing (so it's ``<br>`` instead of
  ``<br />``), and that the contents of ``<script>`` and ``<style>`` elements
  are not escaped.

``text``
  The ``TextSerializer`` produces plain text from markup streams. This is
  useful primarily for `text templates`_, but can also be used to produce
  plain text output from markup templates or other sources.

.. _`text templates`: text-templates.html


Serialization Options
---------------------

Both ``serialize()`` and ``render()`` support additional keyword arguments that
are passed through to the initializer of the serializer class. The following
options are supported by the built-in serializers:

``strip_whitespace``
  Whether the serializer should remove trailing spaces and empty lines.
  Defaults to ``True``.

  (This option is not available for serialization to plain text.)

``doctype``
  A ``(name, pubid, sysid)`` tuple defining the name, publid identifier, and
  system identifier of a ``DOCTYPE`` declaration to prepend to the generated
  output. If provided, this declaration will override any ``DOCTYPE``
  declaration in the stream.

  The parameter can also be specified as a string to refer to commonly used
  doctypes:
  
  +-----------------------------+-------------------------------------------+
  | Shorthand                   | DOCTYPE                                   |
  +=============================+===========================================+
  | ``html`` or                 | HTML 4.01 Strict                          |
  | ``html-strict``             |                                           |
  +-----------------------------+-------------------------------------------+
  | ``html-transitional``       | HTML 4.01 Transitional                    |
  +-----------------------------+-------------------------------------------+
  | ``html-frameset``           | HTML 4.01 Frameset                        |
  +-----------------------------+-------------------------------------------+
  | ``html5``                   | DOCTYPE proposed for the work-in-progress |
  |                             | HTML5 standard                            |
  +-----------------------------+-------------------------------------------+
  | ``xhtml`` or                | XHTML 1.0 Strict                          |
  | ``xhtml-strict``            |                                           |
  +-----------------------------+-------------------------------------------+
  | ``xhtml-transitional``      | XHTML 1.0 Transitional                    |
  +-----------------------------+-------------------------------------------+
  | ``xhtml-frameset``          | XHTML 1.0 Frameset                        |
  +-----------------------------+-------------------------------------------+
  | ``xhtml11``                 | XHTML 1.1                                 |
  +-----------------------------+-------------------------------------------+
  | ``svg`` or ``svg-full``     | SVG 1.1                                   |
  +-----------------------------+-------------------------------------------+
  | ``svg-basic``               | SVG 1.1 Basic                             |
  +-----------------------------+-------------------------------------------+
  | ``svg-tiny``                | SVG 1.1 Tiny                              |
  +-----------------------------+-------------------------------------------+

  (This option is not available for serialization to plain text.)

``namespace_prefixes``
  The namespace prefixes to use for namespace that are not bound to a prefix
  in the stream itself.

  (This option is not available for serialization to HTML or plain text.)

``drop_xml_decl``
  Whether to remove the XML declaration (the ``<?xml ?>`` part at the
  beginning of a document) when serializing. This defaults to ``True`` as an
  XML declaration throws some older browsers into "Quirks" rendering mode.

  (This option is only available for serialization to XHTML.)

``strip_markup``
  Whether the text serializer should detect and remove any tags or entity
  encoded characters in the text.

  (This option is only available for serialization to plain text.)



Using XPath
===========

XPath can be used to extract a specific subset of the stream via the
``select()`` method:

.. code-block:: pycon

  >>> substream = stream.select('a')
  >>> substream
  <genshi.core.Stream object at ...>
  >>> print(substream)
  <a href="http://example.org/">a link</a>

Often, streams cannot be reused: in the above example, the sub-stream is based
on a generator. Once it has been serialized, it will have been fully consumed,
and cannot be rendered again. To work around this, you can wrap such a stream
in a ``list``:

.. code-block:: pycon

  >>> from genshi import Stream
  >>> substream = Stream(list(stream.select('a')))
  >>> substream
  <genshi.core.Stream object at ...>
  >>> print(substream)
  <a href="http://example.org/">a link</a>
  >>> print(substream.select('@href'))
  http://example.org/
  >>> print(substream.select('text()'))
  a link

See `Using XPath in Genshi`_ for more information about the XPath support in
Genshi.

.. _`Using XPath in Genshi`: xpath.html


.. _`event kinds`:

Event Kinds
===========

Every event in a stream is of one of several *kinds*, which also determines
what the ``data`` item of the event tuple looks like. The different kinds of
events are documented below.

.. note:: The ``data`` item is generally immutable. If the data is to be
   modified when processing a stream, it must be replaced by a new tuple.
   Effectively, this means the entire event tuple is immutable.

START
-----
The opening tag of an element.

For this kind of event, the ``data`` item is a tuple of the form
``(tagname, attrs)``, where ``tagname`` is a ``QName`` instance describing the
qualified name of the tag, and ``attrs`` is an ``Attrs`` instance containing
the attribute names and values associated with the tag (excluding namespace
declarations):

.. code-block:: python

  START, (QName('p'), Attrs([(QName('class'), u'intro')])), pos

END
---
The closing tag of an element.

The ``data`` item of end events consists of just a ``QName`` instance
describing the qualified name of the tag:

.. code-block:: python

  END, QName('p'), pos

TEXT
----
Character data outside of elements and comments.

For text events, the ``data`` item should be a unicode object:

.. code-block:: python

  TEXT, u'Hello, world!', pos

START_NS
--------
The start of a namespace mapping, binding a namespace prefix to a URI.

The ``data`` item of this kind of event is a tuple of the form
``(prefix, uri)``, where ``prefix`` is the namespace prefix and ``uri`` is the
full URI to which the prefix is bound. Both should be unicode objects. If the
namespace is not bound to any prefix, the ``prefix`` item is an empty string:

.. code-block:: python

  START_NS, (u'svg', u'http://www.w3.org/2000/svg'), pos

END_NS
------
The end of a namespace mapping.

The ``data`` item of such events consists of only the namespace prefix (a
unicode object):

.. code-block:: python

  END_NS, u'svg', pos

DOCTYPE
-------
A document type declaration.

For this type of event, the ``data`` item is a tuple of the form
``(name, pubid, sysid)``, where ``name`` is the name of the root element,
``pubid`` is the public identifier of the DTD (or ``None``), and ``sysid`` is
the system identifier of the DTD (or ``None``):

.. code-block:: python

  DOCTYPE, (u'html', u'-//W3C//DTD XHTML 1.0 Transitional//EN', \
            u'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'), pos

COMMENT
-------
A comment.

For such events, the ``data`` item is a unicode object containing all character
data between the comment delimiters:

.. code-block:: python

  COMMENT, u'Commented out', pos

PI
--
A processing instruction.

The ``data`` item is a tuple of the form ``(target, data)`` for processing
instructions, where ``target`` is the target of the PI (used to identify the
application by which the instruction should be processed), and ``data`` is text
following the target (excluding the terminating question mark):

.. code-block:: python

  PI, (u'php', u'echo "Yo" '), pos

START_CDATA
-----------
Marks the beginning of a ``CDATA`` section.

The ``data`` item for such events is always ``None``:

.. code-block:: python

  START_CDATA, None, pos

END_CDATA
---------
Marks the end of a ``CDATA`` section.

The ``data`` item for such events is always ``None``:

.. code-block:: python

  END_CDATA, None, pos
