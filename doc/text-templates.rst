.. -*- mode: rst; encoding: utf-8 -*-

=============================
Genshi Text Template Language
=============================

In addition to the XML-based template language, Genshi provides a simple
text-based template language, intended for basic plain text generation needs.
The language is similar to the Django_ template language.

This document describes the template language and will be most useful as
reference to those developing Genshi text templates. Templates are text files of
some kind that include processing directives_ that affect how the template is
rendered, and template expressions that are dynamically substituted by
variable data.

See `Genshi Templating Basics <templates.html>`_ for general information on
embedding Python code in templates.

.. note:: Actually, Genshi currently has two different syntaxes for text
          templates languages: One implemented by the class ``OldTextTemplate``
          and another implemented by ``NewTextTemplate``. This documentation
          concentrates on the latter, which is planned to completely replace the
          older syntax. The older syntax is briefly described under legacy_.

.. _django: http://www.djangoproject.com/


.. _`directives`:

-------------------
Template Directives
-------------------

Directives are template commands enclosed by ``{% ... %}`` characters. They can
affect how the template is rendered in a number of ways: Genshi provides
directives for conditionals and looping, among others.

Each directive must be terminated using an ``{% end %}`` marker. You can add
a string inside the ``{% end %}`` marker, for example to document which
directive is being closed, or even the expression associated with  that
directive. Any text after ``end`` inside the delimiters is  ignored,  and
effectively treated as a comment.

If you want to include a literal delimiter in the output, you need to escape it
by prepending a backslash character (``\``).


Conditional Sections
====================

.. _`if`:

``{% if %}``
------------

The content is only rendered if the expression evaluates to a truth value:

.. code-block:: jinja

  {% if foo %}
    ${bar}
  {% end %}

Given the data ``foo=True`` and ``bar='Hello'`` in the template context, this
would produce::

    Hello


.. _`choose`:
.. _`when`:
.. _`otherwise`:

``{% choose %}``
----------------

The ``choose`` directive, in combination with the directives ``when`` and
``otherwise``, provides advanced contional processing for rendering one of
several alternatives. The first matching ``when`` branch is rendered, or, if
no ``when`` branch matches, the ``otherwise`` branch is be rendered.

If the ``choose`` directive has no argument the nested ``when`` directives will
be tested for truth:

.. code-block:: jinja

  The answer is:
  {% choose %}
    {% when 0 == 1 %}0{% end %}
    {% when 1 == 1 %}1{% end %}
    {% otherwise %}2{% end %}
  {% end %}

This would produce the following output::

  The answer is:
    1

If the ``choose`` does have an argument, the nested ``when`` directives will
be tested for equality to the parent ``choose`` value:

.. code-block:: jinja

  The answer is:
  {% choose 1 %}\
    {% when 0 %}0{% end %}\
    {% when 1 %}1{% end %}\
    {% otherwise %}2{% end %}\
  {% end %}

This would produce the following output::

  The answer is:
      1


Looping
=======

.. _`for`:

``{% for %}``
-------------

The content is repeated for every item in an iterable:

.. code-block:: jinja

  Your items:
  {% for item in items %}\
    * ${item}
  {% end %}

Given ``items=[1, 2, 3]`` in the context data, this would produce::

  Your items
    * 1
    * 2
    * 3


Snippet Reuse
=============

.. _`def`:
.. _`macros`:

``{% def %}``
-------------

The ``def`` directive can be used to create macros, i.e. snippets of template
text that have a name and optionally some parameters, and that can be inserted
in other places:

.. code-block:: jinja

  {% def greeting(name) %}
    Hello, ${name}!
  {% end %}
  ${greeting('world')}
  ${greeting('everyone else')}

The above would be rendered to::

    Hello, world!
    Hello, everyone else!

If a macro doesn't require parameters, it can be defined without the
parenthesis. For example:

.. code-block:: jinja

  {% def greeting %}
    Hello, world!
  {% end %}
  ${greeting()}

The above would be rendered to::

    Hello, world!


.. _includes:
.. _`include`:

``{% include %}``
-----------------

To reuse common parts of template text across template files, you can include
other files using the ``include`` directive:

.. code-block:: jinja

  {% include base.txt %}

Any content included this way is inserted into the generated output. The
included template sees the context data as it exists at the point of the
include. `Macros`_ in the included template are also available to the including
template after the point it was included.

Include paths are relative to the filename of the template currently being
processed. So if the example above was in the file "``myapp/mail.txt``"
(relative to the template search path), the include directive would look for
the included file at "``myapp/base.txt``". You can also use Unix-style
relative paths, for example "``../base.txt``" to look in the parent directory.

Just like other directives, the argument to the ``include`` directive accepts
any Python expression, so the path to the included template can be determined
dynamically:

.. code-block:: jinja

  {% include ${'%s.txt' % filename} %}

Note that a ``TemplateNotFound`` exception is raised if an included file can't
be found.

.. note:: The include directive for text templates was added in Genshi 0.5.


Variable Binding
================

.. _`with`:

``{% with %}``
--------------

The ``{% with %}`` directive lets you assign expressions to variables, which can
be used to make expressions inside the directive less verbose and more
efficient. For example, if you need use the expression ``author.posts`` more
than once, and that actually results in a database query, assigning the results
to a variable using this directive would probably help.

For example:

.. code-block:: jinja

  Magic numbers!
  {% with y=7; z=x+10 %}
    $x $y $z
  {% end %}

Given ``x=42`` in the context data, this would produce::

  Magic numbers!
    42 7 52

Note that if a variable of the same name already existed outside of the scope
of the ``with`` directive, it will **not** be overwritten. Instead, it will
have the same value it had prior to the ``with`` assignment. Effectively,
this means that variables are immutable in Genshi.


.. _whitespace:

---------------------------
White-space and Line Breaks
---------------------------

Note that space or line breaks around directives is never automatically removed.
Consider the following example:

.. code-block:: jinja

  {% for item in items %}
    {% if item.visible %}
      ${item}
    {% end %}
  {% end %}

This will result in two empty lines above and beneath every item, plus the
spaces used for indentation. If you want to supress a line break, simply end
the line with a backslash:

.. code-block:: jinja

  {% for item in items %}\
    {% if item.visible %}\
      ${item}
    {% end %}\
  {% end %}\

Now there would be no empty lines between the items in the output. But you still
get the spaces used for indentation, and because the line breaks are removed,
they actually continue and add up between lines. There are numerous ways to
control white-space in the output while keeping the template readable, such as
moving the indentation into the delimiters, or moving the end delimiter on the
next line, and so on.


.. _comments:

--------
Comments
--------

Parts in templates can be commented out using the delimiters ``{# ... #}``.
Any content in comments are removed from the output.

.. code-block:: jinja

  {# This won't end up in the output #}
  This will.

Just like directive delimiters, these can be escaped by prefixing with a
backslash.

.. code-block:: jinja

  \{# This *will* end up in the output, including delimiters #}
  This too.


.. _legacy:

---------------------------
Legacy Text Template Syntax
---------------------------

The syntax for text templates was redesigned in version 0.5 of Genshi to make
the language more flexible and powerful. The older syntax is based on line
starting with dollar signs, similar to e.g. Cheetah_ or Velocity_.

.. _cheetah: http://cheetahtemplate.org/
.. _velocity: http://jakarta.apache.org/velocity/

A simple template using the old syntax looked like this:

.. code-block:: jinja

  Dear $name,
  
  We have the following items for you:
  #for item in items
   * $item
  #end
  
  All the best,
  Foobar

Beyond the requirement of putting directives on separate lines prefixed with
dollar signs, the language itself is very similar to the new one. Except that
comments are lines that start with two ``#`` characters, and a line-break at the
end of a directive is removed automatically.

.. note:: If you're using this old syntax, it is strongly recommended to
          migrate to the new syntax. Simply replace any references to
          ``TextTemplate`` by ``NewTextTemplate`` (and also change the
          text templates, of course). On the other hand, if you want to stick
          with the old syntax for a while longer, replace references to
          ``TextTemplate`` by ``OldTextTemplate``; while ``TextTemplate`` is
          still an alias for the old language at this point, that will change
          in a future release. But also note that the old syntax may be
          dropped entirely in a future release.
