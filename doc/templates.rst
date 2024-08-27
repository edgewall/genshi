.. -*- mode: rst; encoding: utf-8 -*-

========================
Genshi Templating Basics
========================

Genshi provides a template engine that can be used for generating either
markup (such as HTML_ or XML_) or plain text. While both share some of the
syntax (and much of the underlying implementation) they are essentially
separate languages.

.. _html: http://www.w3.org/html/
.. _xml: http://www.w3.org/XML/

This document describes the common parts of the template engine and will be most
useful as reference to those developing Genshi templates. Templates are XML or
plain text files that include processing directives_ that affect how the
template is rendered, and template expressions_ that are dynamically substituted
by variable data.


--------
Synopsis
--------

A Genshi *markup template* is a well-formed XML document with embedded Python
used for control flow and variable substitution. Markup templates should be
used to generate any kind of HTML or XML output, as they provide a number of
advantages over simple text-based templates (such as automatic escaping of
variable data).

The following is a simple Genshi markup template:

.. code-block:: genshi

  <?python
    title = "A Genshi Template"
    fruits = ["apple", "orange", "kiwi"]
  ?>
  <html xmlns:py="http://genshi.edgewall.org/">
    <head>
      <title py:content="title">This is replaced.</title>
    </head>

    <body>
      <p>These are some of my favorite fruits:</p>
      <ul>
        <li py:for="fruit in fruits">
          I like ${fruit}s
        </li>
      </ul>
    </body>
  </html>

This example shows:

(a) a Python code block in a processing instruction
(b) the Genshi namespace declaration
(c) usage of templates directives (``py:content`` and ``py:for``)
(d) an inline Python expression (``${fruit}``).

The template would generate output similar to this:

.. code-block:: genshi

  <html>
    <head>
      <title>A Genshi Template</title>
    </head>

    <body>
      <p>These are some of my favorite fruits:</p>
      <ul>
        <li>I like apples</li>
        <li>I like oranges</li>
        <li>I like kiwis</li>
      </ul>
    </body>
  </html>

A *text template* is a simple plain text document that can also contain
embedded Python code. Text templates are intended to be used for simple
*non-markup* text formats, such as the body of an plain text email. For
example:

.. code-block:: genshitext

  Dear $name,
  
  These are some of my favorite fruits:
  #for fruit in fruits
   * $fruit
  #end


----------
Python API
----------

The Python code required for templating with Genshi is generally based on the
following pattern:

* Attain a ``MarkupTemplate`` or ``TextTemplate`` object from a string or
  file-like object containing the template source. This can either be done
  directly, or through a ``TemplateLoader`` instance.
* Call the ``generate()`` method of the template, passing any data that should
  be made available to the template as keyword arguments.
* Serialize the resulting stream using its ``render()`` method.

For example:

.. code-block:: pycon

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<h1>Hello, $name!</h1>')
  >>> stream = tmpl.generate(name='world')
  >>> print(stream.render('xhtml'))
  <h1>Hello, world!</h1>

.. note:: See the Serialization_ section of the `Markup Streams`_ page for
          information on configuring template output options.

Using a text template is similar:

.. code-block:: pycon

  >>> from genshi.template import TextTemplate
  >>> tmpl = TextTemplate('Hello, $name!')
  >>> stream = tmpl.generate(name='world')
  >>> print(stream)
  Hello, world!

.. note:: If you want to use text templates, you should consider using the
          ``NewTextTemplate`` class instead of simply ``TextTemplate``. See
          the `Text Template Language`_ page.

.. _serialization: streams.html#serialization
.. _`Text Template Language`: text-templates.html
.. _`Markup Streams`: streams.html

Using a `template loader`_ provides the advantage that “compiled” templates are
automatically cached, and only parsed again when the template file changes. In
addition, it enables the use of a *template search path*, allowing template
directories to be spread across different file-system locations. Using a
template loader would generally look as follows:

.. code-block:: python

  from genshi.template import TemplateLoader
  loader = TemplateLoader([templates_dir1, templates_dir2])
  tmpl = loader.load('test.html')
  stream = tmpl.generate(title='Hello, world!')
  print(stream.render())

See the `API documentation <api/index.html>`_ for details on using Genshi via
the Python API.

.. _`template loader`: loader.html

.. _`expressions`:

------------------------------------
Template Expressions and Code Blocks
------------------------------------

Python_ expressions can be used in text and directive arguments. An expression
is substituted with the result of its evaluation against the template data.
Expressions in text (which includes the values of non-directive attributes) need
to prefixed with a dollar sign (``$``) and usually enclosed in curly braces
(``{…}``).

.. _python: http://www.python.org/

If the expression starts with a letter and contains only letters, digits, dots,
and underscores, the curly braces may be omitted. In all other cases, the
braces are required so that the template processor knows where the expression
ends:

.. code-block:: pycon

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<em>${items[0].capitalize()} item</em>')
  >>> print(tmpl.generate(items=['first', 'second']))
  <em>First item</em>

Expressions support the full power of Python. In addition, it is possible to
access items in a dictionary using “dotted notation” (i.e. as if they were
attributes), and vice-versa (i.e. access attributes as if they were items in a
dictionary):

.. code-block:: pycon

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<em>${dict.foo}</em>')
  >>> print(tmpl.generate(dict={'foo': 'bar'}))
  <em>bar</em>

Because there are two ways to access either attributes or items, expressions
do not raise the standard ``AttributeError`` or ``IndexError`` exceptions, but
rather an exception of the type ``UndefinedError``. The same kind of error is
raised when you try to use a top-level variable that is not in the context data.
See `Error Handling`_ below for details on how such errors are handled.


Escaping
========

If you need to include a literal dollar sign in the output where Genshi would
normally detect an expression, you can simply add another dollar sign:

.. code-block:: pycon

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<em>$foo</em>') # Wanted "$foo" as literal output
  >>> print(tmpl.generate())
  Traceback (most recent call last):
    ...
  UndefinedError: "foo" not defined
  >>> tmpl = MarkupTemplate('<em>$$foo</em>')
  >>> print(tmpl.generate())
  <em>$foo</em>

But note that this is not necessary if the characters following the dollar sign
do not qualify as an expression. For example, the following needs no escaping:

.. code-block:: pycon

  >>> tmpl = MarkupTemplate('<script>$(function() {})</script>')
  >>> print(tmpl.generate())
  <script>$(function() {})</script>

On the other hand, Genshi will always replace two dollar signs in text with a
single dollar sign, so you'll need to use three dollar signs to get two in the
output:

.. code-block:: pycon

  >>> tmpl = MarkupTemplate('<script>$$$("div")</script>')
  >>> print(tmpl.generate())
  <script>$$("div")</script>


.. _`code blocks`:

Code Blocks
===========

Templates also support full Python code blocks, using the ``<?python ?>``
processing instruction in XML templates:

.. code-block:: genshi

  <div>
    <?python
        from genshi.builder import tag
        def greeting(name):
            return tag.b('Hello, %s!' % name) ?>
    ${greeting('world')}
  </div>

This will produce the following output:

.. code-block:: xml

  <div>
    <b>Hello, world!</b>
  </div>

In text templates (although only those using the new syntax introduced in
Genshi 0.5), code blocks use the special ``{% python %}`` directive:

.. code-block:: genshitext

  {% python
      from genshi.builder import tag
      def greeting(name):
          return 'Hello, %s!' % name
  %}
  ${greeting('world')}

This will produce the following output::

  Hello, world!


Code blocks can import modules, define classes and functions, and basically do
anything you can do in normal Python code. What code blocks can *not* do is to
produce content that is emitted directly tp the generated output.

.. note:: Using the ``print`` statement will print to the standard output
          stream, just as it does for other Python code in your application.

Unlike expressions, Python code in ``<?python ?>`` processing instructions can
not use item and attribute access in an interchangeable manner. That means that
“dotted notation” is always attribute access, and vice-versa.

The support for Python code blocks in templates is not supposed to encourage
mixing application code into templates, which is generally considered bad
design. If you're using many code blocks, that may be a sign that you should
move such code into separate Python modules.

If you'd rather not allow the use of Python code blocks in templates, you can
simply set the ``allow_exec`` parameter (available on the ``Template`` and the
``TemplateLoader`` initializers) to ``False``. In that case Genshi will raise
a syntax error when a ``<?python ?>`` processing instruction is encountered.
But please note that disallowing code blocks in templates does not turn Genshi
into a sandboxable template engine; there are sufficient ways to do harm even
using plain expressions.


.. _`error handling`:

Error Handling
==============

By default, Genshi raises an ``UndefinedError`` if a template expression
attempts to access a variable that is not defined:

.. code-block:: pycon

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<p>${doh}</p>')
  >>> tmpl.generate().render('xhtml')
  Traceback (most recent call last):
    ...
  UndefinedError: "doh" not defined

You can change this behavior by setting the variable lookup mode to "lenient".
In that case, accessing undefined variables returns an `Undefined` object,
meaning that the expression does not fail immediately. See below for details.

If you need to check whether a variable exists in the template context, use the
defined_ or the value_of_ function described below. To check for existence of
attributes on an object, or keys in a dictionary, use the ``hasattr()``,
``getattr()`` or ``get()`` functions, or the ``in`` operator, just as you would
in regular Python code:

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<p>${defined("doh")}</p>')
  >>> print(tmpl.generate().render('xhtml'))
  <p>False</p>

.. note:: Lenient error handling was the default in Genshi prior to version 0.5.
          Strict mode was introduced in version 0.4, and became the default in
          0.5. The reason for this change was that the lenient error handling
          was masking actual errors in templates, thereby also making it harder
          to debug some problems.


.. _`lenient`:

Lenient Mode
------------

If you instruct Genshi to use the lenient variable lookup mode, it allows you
to access variables that are not defined, without raising an ``UndefinedError``.

This mode can be chosen by passing the ``lookup='lenient'`` keyword argument to
the template initializer, or by passing the ``variable_lookup='lenient'``
keyword argument to the ``TemplateLoader`` initializer:

.. code-block:: pycon

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<p>${doh}</p>', lookup='lenient')
  >>> print(tmpl.generate().render('xhtml'))
  <p></p>

You *will* however get an exception if you try to call an undefined variable, or
do anything else with it, such as accessing its attributes:

.. code-block:: pycon

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<p>${doh.oops}</p>', lookup='lenient')
  >>> print(tmpl.generate().render('xhtml'))
  Traceback (most recent call last):
    ...
  UndefinedError: "doh" not defined

If you need to know whether a variable is defined, you can check its type
against the ``Undefined`` class, for example in a conditional directive:

.. code-block:: pycon

  >>> from genshi.template import MarkupTemplate
  >>> tmpl = MarkupTemplate('<p>${type(doh) is not Undefined}</p>',
  ...                       lookup='lenient')
  >>> print(tmpl.generate().render('xhtml'))
  <p>False</p>

Alternatively, the built-in functions defined_ or value_of_ can be used in this
case.

Custom Modes
------------

In addition to the built-in "lenient" and "strict" modes, it is also possible to
use a custom error handling mode. For example, you could use lenient error
handling in a production environment, while also logging a warning when an
undefined variable is referenced.

See the API documentation of the ``genshi.template.eval`` module for details.


Built-in Functions & Types
==========================

The following functions and types are available by default in template code, in
addition to the standard built-ins that are available to all Python code.

.. _`defined`:

``defined(name)``
-----------------
This function determines whether a variable of the specified name exists in
the context data, and returns ``True`` if it does.
 
.. _`value_of`:

``value_of(name, default=None)``
--------------------------------
This function returns the value of the variable with the specified name if
such a variable is defined, and returns the value of the ``default``
parameter if no such variable is defined.

.. _`Markup`:

``Markup(text)``
----------------
The ``Markup`` type marks a given string as being safe for inclusion in markup,
meaning it will *not* be escaped in the serialization stage. Use this with care,
as not escaping a user-provided string may allow malicious users to open your
web site to cross-site scripting attacks.

.. _`Undefined`:

``Undefined``
----------------
The ``Undefined`` type can be used to check whether a reference variable is
defined, as explained in `error handling`_.


.. _`directives`:

-------------------
Template Directives
-------------------

Directives provide control flow functionality for templates, such as conditions
or iteration. As the syntax for directives depends on whether you're using
markup or text templates, refer to the
`XML Template Language <xml-templates.html>`_ or
`Text Template Language <text-templates.html>`_ pages for information.
