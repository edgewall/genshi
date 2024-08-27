.. -*- mode: rst; encoding: utf-8 -*-

============================
Genshi XML Template Language
============================

Genshi provides a XML-based template language that is heavily inspired by Kid_,
which in turn was inspired by a number of existing template languages, namely
XSLT_, TAL_, and PHP_.

.. _kid: http://kid-templating.org/
.. _python: http://www.python.org/
.. _xslt: http://www.w3.org/TR/xslt
.. _tal: http://www.zope.org/Wikis/DevSite/Projects/ZPT/TAL
.. _php: http://www.php.net/

This document describes the template language and will be most useful as
reference to those developing Genshi XML templates. Templates are XML files of
some kind (such as XHTML) that include processing directives_ (elements or
attributes identified by a separate namespace) that affect how the template is
rendered, and template expressions that are dynamically substituted by
variable data.

See `Genshi Templating Basics <templates.html>`_ for general information on
embedding Python code in templates.


.. _`directives`:

-------------------
Template Directives
-------------------

Directives are elements and/or attributes in the template that are identified
by the namespace ``http://genshi.edgewall.org/``. They can affect how the
template is rendered in a number of ways: Genshi provides directives for
conditionals and looping, among others.

To use directives in a template, the namespace must be declared, which is
usually done on the root element:

.. code-block:: html+genshi

  <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:py="http://genshi.edgewall.org/"
        lang="en">
    ...
  </html>

In this example, the default namespace is set to the XHTML namespace, and the
namespace for Genshi directives is bound to the prefix “py”.

All directives can be applied as attributes, and some can also be used as
elements. The ``if`` directives for conditionals, for example, can be used in
both ways:

.. code-block:: html+genshi

  <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:py="http://genshi.edgewall.org/"
        lang="en">
    ...
    <div py:if="foo">
      <p>Bar</p>
    </div>
    ...
  </html>

This is basically equivalent to the following:

.. code-block:: html+genshi

  <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:py="http://genshi.edgewall.org/"
        lang="en">
    ...
    <py:if test="foo">
      <div>
        <p>Bar</p>
      </div>
    </py:if>
    ...
  </html>

The rationale behind the second form is that directives do not always map
naturally to elements in the template. In such cases, the ``py:strip``
directive can be used to strip off the unwanted element, or the directive can
simply be used as an element.


Conditional Sections
====================

.. _`py:if`:

``py:if``
---------

The element and its content is only rendered if the expression evaluates to a
truth value:

.. code-block:: html+genshi

  <div>
    <b py:if="foo">${bar}</b>
  </div>

Given the data ``foo=True`` and ``bar='Hello'`` in the template context, this
would produce:

.. code-block:: xml

  <div>
    <b>Hello</b>
  </div>

But setting ``foo=False`` would result in the following output:

.. code-block:: xml

  <div>
  </div>

This directive can also be used as an element:

.. code-block:: html+genshi

  <div>
    <py:if test="foo">
      <b>${bar}</b>
    </py:if>
  </div>

.. _`py:choose`:
.. _`py:when`:
.. _`py:otherwise`:

``py:choose``
-------------

The ``py:choose`` directive, in combination with the directives ``py:when``
and ``py:otherwise`` provides advanced conditional processing for rendering one
of several alternatives. The first matching ``py:when`` branch is rendered, or,
if no ``py:when`` branch matches, the ``py:otherwise`` branch is rendered.

If the ``py:choose`` directive is empty the nested ``py:when`` directives will
be tested for truth:

.. code-block:: html+genshi

  <div py:choose="">
    <span py:when="0 == 1">0</span>
    <span py:when="1 == 1">1</span>
    <span py:otherwise="">2</span>
  </div>

This would produce the following output:

.. code-block:: xml

  <div>
    <span>1</span>
  </div>

If the ``py:choose`` directive contains an expression the nested ``py:when``
directives will be tested for equality to the parent ``py:choose`` value:

.. code-block:: html+genshi

  <div py:choose="1">
    <span py:when="0">0</span>
    <span py:when="1">1</span>
    <span py:otherwise="">2</span>
  </div>

This would produce the following output:

.. code-block:: xml

  <div>
    <span>1</span>
  </div>

These directives can also be used as elements:

.. code-block:: html+genshi

  <py:choose test="1">
    <py:when test="0">0</py:when>
    <py:when test="1">1</py:when>
    <py:otherwise>2</py:otherwise>
  </py:choose>

Looping
=======

.. _`py:for`:

``py:for``
----------

The element is repeated for every item in an iterable:

.. code-block:: html+genshi

  <ul>
    <li py:for="item in items">${item}</li>
  </ul>

Given ``items=[1, 2, 3]`` in the context data, this would produce:

.. code-block:: xml

  <ul>
    <li>1</li><li>2</li><li>3</li>
  </ul>

This directive can also be used as an element:

.. code-block:: html+genshi

  <ul>
    <py:for each="item in items">
      <li>${item}</li>
    </py:for>
  </ul>


Snippet Reuse
=============

.. _`py:def`:
.. _`macros`:

``py:def``
----------

The ``py:def`` directive can be used to create macros, i.e. snippets of
template code that have a name and optionally some parameters, and that can be
inserted in other places:

.. code-block:: html+genshi

  <div>
    <p py:def="greeting(name)" class="greeting">
      Hello, ${name}!
    </p>
    ${greeting('world')}
    ${greeting('everyone else')}
  </div>

The above would be rendered to:

.. code-block:: xml

  <div>
    <p class="greeting">
      Hello, world!
    </p>
    <p class="greeting">
      Hello, everyone else!
    </p>
  </div>

If a macro doesn't require parameters, it can be defined without the 
parenthesis. For example:

.. code-block:: html+genshi

  <div>
    <p py:def="greeting" class="greeting">
      Hello, world!
    </p>
    ${greeting()}
  </div>

The above would be rendered to:

.. code-block:: xml

  <div>
    <p class="greeting">
      Hello, world!
    </p>
  </div>

This directive can also be used as an element:

.. code-block:: html+genshi

  <div>
    <py:def function="greeting(name)">
      <p class="greeting">Hello, ${name}!</p>
    </py:def>
  </div>


.. _Match Templates:
.. _`py:match`:

``py:match``
------------

This directive defines a *match template*: given an XPath expression, it
replaces any element in the template that matches the expression with its own
content.

For example, the match template defined in the following template matches any
element with the tag name “greeting”:

.. code-block:: html+genshi

  <div>
    <span py:match="greeting">
      Hello ${select('@name')}
    </span>
    <greeting name="Dude" />
  </div>

This would result in the following output:

.. code-block:: xml

  <div>
    <span>
      Hello Dude
    </span>
  </div>

Inside the body of a ``py:match`` directive, the ``select(path)`` function is
made available so that parts or all of the original element can be incorporated
in the output of the match template. See `Using XPath`_ for more information
about this function.

.. _`Using XPath`: streams.html#using-xpath

Match templates are applied both to the original markup as well to the
generated markup. The order in which they are applied depends on the order
they are declared in the template source: a match template defined after
another match template is applied to the output generated by the first match
template. The match templates basically form a pipeline.

This directive can also be used as an element:

.. code-block:: html+genshi

  <div>
    <py:match path="greeting">
      <span>Hello ${select('@name')}</span>
    </py:match>
    <greeting name="Dude" />
  </div>

When used this way, the ``py:match`` directive can also be annotated with a
couple of optimization hints. For example, the following informs the matching
engine that the match should only be applied once:

.. code-block:: html+genshi

  <py:match path="body" once="true">
    <body py:attrs="select('@*')">
      <div id="header">...</div>
      ${select("*|text()")}
      <div id="footer">...</div>
    </body>
  </py:match>

The following optimization hints are recognized:

+---------------+-----------+-----------------------------------------------+
| Attribute     | Default   | Description                                   |
+===============+===========+===============================================+
| ``buffer``    | ``true``  | Whether the matched content should be         |
|               |           | buffered in memory. Buffering can improve     |
|               |           | performance a bit at the cost of needing more |
|               |           | memory during rendering. Buffering is         |
|               |           | ''required'' for match templates that contain |
|               |           | more than one invocation of the ``select()``  |
|               |           | function. If there is only one call, and the  |
|               |           | matched content can potentially be very long, |
|               |           | consider disabling buffering to avoid         |
|               |           | excessive memory use.                         |
+---------------+-----------+-----------------------------------------------+
| ``once``      | ``false`` | Whether the engine should stop looking for    |
|               |           | more matching elements after the first match. |
|               |           | Use this on match templates that match        |
|               |           | elements that can only occur once in the      |
|               |           | stream, such as the ``<head>`` or ``<body>``  |
|               |           | elements in an HTML template, or elements     |
|               |           | with a specific ID.                           |
+---------------+-----------+-----------------------------------------------+
| ``recursive`` | ``true``  | Whether the match template should be applied  |
|               |           | to its own output. Note that ``once`` implies |
|               |           | non-recursive behavior, so this attribute     |
|               |           | only needs to be set for match templates that |
|               |           | don't also have ``once`` set.                 |
+---------------+-----------+-----------------------------------------------+

.. note:: The ``py:match`` optimization hints were added in the 0.5 release. In
          earlier versions, the attributes have no effect.


Variable Binding
================

.. _`with`:

``py:with``
-----------

The ``py:with`` directive lets you assign expressions to variables, which can
be used to make expressions inside the directive less verbose and more
efficient. For example, if you need use the expression ``author.posts`` more
than once, and that actually results in a database query, assigning the results
to a variable using this directive would probably help.

For example:

.. code-block:: html+genshi

  <div>
    <span py:with="y=7; z=x+10">$x $y $z</span>
  </div>

Given ``x=42`` in the context data, this would produce:

.. code-block:: xml

  <div>
    <span>42 7 52</span>
  </div>

This directive can also be used as an element:

.. code-block:: html+genshi

  <div>
    <py:with vars="y=7; z=x+10">$x $y $z</py:with>
  </div>

Note that if a variable of the same name already existed outside of the scope
of the ``py:with`` directive, it will **not** be overwritten. Instead, it
will have the same value it had prior to the ``py:with`` assignment.
Effectively, this means that variables are immutable in Genshi.


Structure Manipulation
======================

.. _`py:attrs`:

``py:attrs``
------------

This directive adds, modifies or removes attributes from the element:

.. code-block:: html+genshi

  <ul>
    <li py:attrs="foo">Bar</li>
  </ul>

Given ``foo={'class': 'collapse'}`` in the template context, this would
produce:

.. code-block:: xml

  <ul>
    <li class="collapse">Bar</li>
  </ul>

Attributes with the value ``None`` are omitted, so given ``foo={'class': None}``
in the context for the same template this would produce:

.. code-block:: xml

  <ul>
    <li>Bar</li>
  </ul>

This directive can only be used as an attribute.


.. _`py:content`:

``py:content``
--------------

This directive replaces any nested content with the result of evaluating the
expression:

.. code-block:: html+genshi

  <ul>
    <li py:content="bar">Hello</li>
  </ul>

Given ``bar='Bye'`` in the context data, this would produce:

.. code-block:: xml

  <ul>
    <li>Bye</li>
  </ul>

This directive can only be used as an attribute.


.. _`py:replace`:

``py:replace``
--------------

This directive replaces the element itself with the result of evaluating the
expression:

.. code-block:: html+genshi

  <div>
    <span py:replace="bar">Hello</span>
  </div>

Given ``bar='Bye'`` in the context data, this would produce:

.. code-block:: xml

  <div>
    Bye
  </div>

This directive can also be used as an element (since version 0.5):

.. code-block:: html+genshi

  <div>
    <py:replace value="title">Placeholder</py:replace>
  </div>



.. _`py:strip`:

``py:strip``
------------

This directive conditionally strips the top-level element from the output. When
the value of the ``py:strip`` attribute evaluates to ``True``, the element is
stripped from the output:

.. code-block:: html+genshi

  <div>
    <div py:strip="True"><b>foo</b></div>
  </div>

This would be rendered as:

.. code-block:: xml

  <div>
    <b>foo</b>
  </div>

As a shorthand, if the value of the ``py:strip`` attribute is empty, that has
the same effect as using a truth value (i.e. the element is stripped).


.. _order:

Processing Order
================

It is possible to attach multiple directives to a single element, although not
all combinations make sense. When multiple directives are encountered, they are
processed in the following order:

#. `py:def`_
#. `py:match`_
#. `py:when`_
#. `py:otherwise`_
#. `py:for`_
#. `py:if`_
#. `py:choose`_
#. `py:with`_
#. `py:replace`_
#. `py:content`_
#. `py:attrs`_
#. `py:strip`_


.. _includes:

--------
Includes
--------

To reuse common snippets of template code, you can include other files using
XInclude_.

.. _xinclude: http://www.w3.org/TR/xinclude/

For this, you need to declare the XInclude namespace (commonly bound to the
prefix “xi”) and use the ``<xi:include>`` element where you want the external
file to be pulled in:

.. code-block:: html+genshi

  <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:py="http://genshi.edgewall.org/"
        xmlns:xi="http://www.w3.org/2001/XInclude">
    <xi:include href="base.html" />
    ...
  </html>

Include paths are relative to the filename of the template currently being
processed. So if the example above was in the file "``myapp/index.html``"
(relative to the template search path), the XInclude processor would look for
the included file at "``myapp/base.html``". You can also use Unix-style
relative paths, for example "``../base.html``" to look in the parent directory.

Any content included this way is inserted into the generated output instead of
the ``<xi:include>`` element. The included template sees the same context data.
`Match templates`_ and `macros`_ in the included template are also available to
the including template after the point it was included.

By default, an error will be raised if an included file is not found. If that's
not what you want, you can specify fallback content that should be used if the
include fails. For example, to to make the include above fail silently, you'd
write:

.. code-block:: html+genshi

  <xi:include href="base.html"><xi:fallback /></xi:include>

See the `XInclude specification`_ for more about fallback content. Note though 
that Genshi currently only supports a small subset of XInclude.

.. _`xinclude specification`: http://www.w3.org/TR/xinclude/


Dynamic Includes
================

Incudes in Genshi are fully dynamic: Just like normal attributes, the `href`
attribute accepts expressions, and directives_ can be used on the
``<xi:include />`` element just as on any other element, meaning you can do
things like conditional includes:

.. code-block:: html+genshi

  <xi:include href="${name}.html" py:if="not in_popup"
              py:for="name in ('foo', 'bar', 'baz')" />


Including Text Templates
========================

The ``parse`` attribute of the ``<xi:include>`` element can be used to specify
whether the included template is an XML template or a text template (using the
new syntax added in Genshi 0.5):

.. code-block:: html+genshi

  <xi:include href="myscript.js" parse="text" />

This example would load the ``myscript.js`` file as a ``NewTextTemplate``. See
`text templates`_ for details on the syntax of text templates.

.. _`text templates`: text-templates.html


.. _comments:

--------
Comments
--------

Normal XML/HTML comment syntax can be used in templates:

.. code-block:: html+genshi

  <!-- this is a comment -->

However, such comments get passed through the processing pipeline and are by
default included in the final output. If that's not desired, prefix the comment
text with an exclamation mark:

.. code-block:: html+genshi

  <!-- !this is a comment too, but one that will be stripped from the output -->

Note that it does not matter whether there's whitespace before or after the
exclamation mark, so the above could also be written as follows:

.. code-block:: html+genshi

  <!--! this is a comment too, but one that will be stripped from the output -->
