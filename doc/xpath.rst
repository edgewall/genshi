.. -*- mode: rst; encoding: utf-8 -*-

=====================
Using XPath in Genshi
=====================

Genshi provides basic XPath_ support for matching and querying event streams.

.. _xpath: http://www.w3.org/TR/xpath


-----------
Limitations
-----------

Due to the streaming nature of the processing model, Genshi uses only a subset
of the `XPath 1.0`_ language.

.. _`XPath 1.0`: http://www.w3.org/TR/xpath

In particular, only the following axes are supported:

* ``attribute``
* ``child``
* ``descendant``
* ``descendant-or-self``
* ``self``

This means you can't use the ``parent``, ancestor, or sibling axes in Genshi
(the ``namespace`` axis isn't supported either, but what you'd ever need that
for I don't know). Basically, any path expression that would require buffering
of the stream is not supported.

Predicates are of course supported, but path expressions *inside* predicates
are restricted to attribute lookups (again due to the lack of buffering).

Most of the XPath functions and operators are supported, however they
(currently) only work inside predicates. The following functions are **not**
supported:

* ``count()``
* ``id()``
* ``lang()``
* ``last()``
* ``position()``
* ``string()``
* ``sum()``

The mathematical operators (``+``, ``-``, ``*``, ``div``, and ``mod``) are not
yet supported, whereas sub-expressions and the various comparison and logical
operators should work as expected.

You can also use XPath variable references (``$var``) inside predicates.


----------------
Querying Streams
----------------

The ``Stream`` class provides a ``select(path)`` function that can be used to
retrieve subsets of the stream:

.. code-block:: pycon

  >>> from genshi.input import XML

  >>> doc = XML('''<doc>
  ...  <items count="4">
  ...       <item status="new">
  ...         <summary>Foo</summary>
  ...       </item>
  ...       <item status="closed">
  ...         <summary>Bar</summary>
  ...       </item>
  ...       <item status="closed" resolution="invalid">
  ...         <summary>Baz</summary>
  ...       </item>
  ...       <item status="closed" resolution="fixed">
  ...         <summary>Waz</summary>
  ...       </item>
  ...   </items>
  ... </doc>''')

  >>> print(doc.select('items/item[@status="closed" and '
  ...     '(@resolution="invalid" or not(@resolution))]/summary/text()'))
  BarBaz



---------------------
Matching in Templates
---------------------

See the directive ``py:match`` in the `XML Template Language Specification`_.

.. _`XML Template Language Specification`: xml-templates.html
