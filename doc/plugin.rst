.. -*- mode: rst; encoding: utf-8 -*-

===========================
Using the Templating Plugin
===========================

While you can easily use Genshi templating through the APIs provided directly
by Genshi, in some situations you may want to use Genshi through the template
engine plugin API. Note though that this considerably limits the power and
flexibility of Genshi templates (for example, there's no good way to use filters
such as Genshi's :ref:`HTMLFormFiller` when the plugin
API is sitting between your code and Genshi).


Introduction
============

Some Python web frameworks support a variety of different templating engines
through the `Template Engine Plugin API`_, which was first developed by the
Buffet_ and TurboGears_ projects.

.. _`Template Engine Plugin API`: http://docs.turbogears.org/1.0/TemplatePlugins
.. _`Buffet`: http://projects.dowski.com/projects/buffet
.. _`TurboGears`: http://www.turbogears.org/

Genshi supports this API out of the box, so you can use it in frameworks like
TurboGears or `Pylons`_ without installing any additional packages. A small
example TurboGears application is included in the ``examples`` directory of
source distributions of Genshi.

.. _`Pylons`: http://pylonshq.com/


Usage
=====

The way you use Genshi through the plugin API depends very much on the framework
you're using. In general, the approach will look something like the following:

(1) Configure Genshi as the default (or an additional) template engine
(2) Optionally specify Genshi-specific `configuration options`_
(3) For any given *view* or *controller* (or whatever those are called in your
    framework of choice), specify the name of the template to use and which data
    should be made available to it.

For point 1, you'll have to specify the *name* of the template engine plugin.
For Genshi, this is **"genshi"**. However, because Genshi supports both markup
and text templates, it also provides two separate plugins, namely
**"genshi-markup"** and **"genshi-text"** (the "genshi" name is just an
alias for "genshi-markup").

Usually, you can choose a default template engine, but also use a different
engine on a per-request basis. So to use markup templates in general, but a text
template in a specific controller, you'd configure "genshi" as the default
template engine, and specify "genshi-text" for the controllers that should use
text templates. How exactly this works depends on the framework in use.

When rendering a specific template in a controller (point 3 above), you may also
be able to pass additional options to the plugin. This includes the ``format``
keyword argument, which Genshi will use to override the configured default
serialization method. In combination with specifying the "genshi-text" engine
name as explained above, you would use this to specify the "text" serialization
method when you want to use a text template. Or you'd specify "xml" for the
format when you want to produce an Atom feed or other XML content.


Template Paths
--------------

How you specify template paths depends on whether you have a `search path`_ set
up or not. The search path is a list of directories that Genshi should load
templates from. Now when you request a template using a relative path such as
``mytmpl.html`` or ``foo/mytmpl.html``, Genshi will look for that file in the
directories on the search path.

For mostly historical reasons, the Genshi template engine plugin uses a
different approach when you **haven't** configured the template search path:
you now load templates using *dotted notation*, for example ``mytmpl`` or
``foo.mytmpl``.  Note how you've lost the ability to explicitly specify the
file extension: you now have to use ``.html`` for markup templates, and
``.txt`` for text templates.

Using the search path is recommended for a number of reasons: First, it's
the native Genshi model and is thus more robust and better supported.
Second, a search path gives you much more flexibility for organizing your
application templates. And as noted above, you aren't forced to use hardcoded
filename extensions for your template files.


Extra Implicit Objects
----------------------

The "genshi-markup" template engine plugin adds some extra functions that are
made available to all templates implicitly, namely:

``HTML(string)``
  Parses the given string as HTML and returns a markup stream.
``XML(string)``
  Parses the given string as XML and returns a markup stream.
``ET(tree)``
  Adapts the given `ElementTree`_ object to a markup stream.

The framework may make additional objects available by default. Consult the
documentation of your framework for more information.

.. _elementtree: http://effbot.org/zone/element-index.htm


.. _`configuration options`:

Configuration Options
=====================

The plugin API allows plugins to be configured using a dictionary of strings.
The following is a list of configuration options that Genshi supports. These may
or may not be made available by your framework. TurboGears 1.0, for example,
only passes a fixed set of options to all plugins.

``genshi.allow_exec``
--------------------------
Whether the Python code blocks should be permitted in templates. Specify "yes"
to allow code blocks (which is the default), or "no" otherwise. Please note
that disallowing code blocks in templates does not turn Genshi into a
sandboxable template engine; there are sufficient ways to do harm even using
plain expressions.

``genshi.auto_reload``
----------------------
Whether the template loader should check the last modification time of template 
files, and automatically reload them if they have been changed. Specify "yes"
to enable this reloading (which is the default), or "no" to turn it off.

You probably want to disable reloading in a production environment to improve
performance of both templating loading and the processing of includes. But
remember that you'll then have to manually restart the server process anytime
the templates are updated.

``genshi.default_doctype``
--------------------------
The default ``DOCTYPE`` declaration to use in generated markup. Valid values
are:

**html-strict** (or just **html**)
  HTML 4.01 Strict
**html-transitional**
  HTML 4.01 Transitional
**xhtml-strict** (or just **xhtml**)
  XHTML 1.0 Strict
**xhtml-transitional**
  XHTML 1.0 Transitional
**html5**
  HTML5 (as `proposed`_ by the WHAT-WG)

.. _proposed: http://www.whatwg.org/specs/web-apps/current-work/

.. note:: While using the Genshi API directly allows you to specify document
          types not in that list, the *dictionary-of-strings* based
          configuration utilized by the plugin API unfortunately limits your
          choices to those listed above.

The default behavior is to not do any prepending/replacing of a ``DOCTYPE``, but
rather pass through those defined in the templates (if any). If this option is
set, however, any ``DOCTYPE`` declarations in the templates are replaced by the
specified document type.

Note that with (X)HTML, the presence and choice of the ``DOCTYPE`` can have a
more or less dramatic impact on how modern browsers render pages that use CSS
style sheets. In particular, browsers may switch to *quirks rendering mode* for
certain document types, or when the ``DOCTYPE`` declaration is missing
completely.

For more information on the choice of the appropriate ``DOCTYPE``, see:

* `Recommended DTDs to use in your Web document <http://www.w3.org/QA/2002/04/valid-dtd-list.html>`_
* `Choosing a DOCTYPE <http://htmlhelp.com/tools/validator/doctype.html>`_

``genshi.default_encoding``
---------------------------
The default output encoding to use when serializing a template. By default,
Genshi uses UTF-8. If you need to, you can choose a different charset by
specifying this option, although that rarely makes sense.

As Genshi is not in control over what HTTP headers are being sent together with
the template output, make sure that you (or the framework you're using)
specify the chosen encoding as part of the outgoing ``Content-Type`` header.
For example::

  Content-Type: text/html; charset=utf-8

.. note:: Browsers commonly use ISO-8859-1 by default for ``text/html``, so even
          if you use Genshi's default UTF-8 encoding, you'll have to let the
          browser know about that explicitly

``genshi.default_format``
-------------------------
Determines the default serialization method to use. Valid options are:

**xml**
  Serialization to XML
**xhtml**
  Serialization to XHTML in a way that should be compatible with HTML (i.e. the
  result can be sent using the ``text/html`` MIME type, but can also be handled
  by XML parsers if you're careful).
**html**
  Serialization to HTML
**text**
  Plain text serialization

See `Understanding HTML, XML and XHTML`_ for an excellent description of the
subtle differences between the three different markup serialization options. As
a general recommendation, if you don't have a special requirement to produce
well-formed XML, you should probably use the **html** option for your web sites.

.. _`Understanding HTML, XML and XHTML`: http://webkit.org/blog/?p=68

``genshi.loader_callback``
--------------------------
The callback function that should be invoked whenever the template loader loads
a new template.

.. note:: Unlike the other options, this option can **not** be passed as
          a string value, but rather must be a reference to the actual function.
          That effectively means it can not be set from (non-Python)
          configuration files.

``genshi.lookup_errors``
------------------------
The error handling style to use in template expressions. Can be either
**lenient** (the default) or **strict**. See the `Error Handling`_ section for
detailled information on the differences between these two modes.

.. _`Error Handling`: templates.html#template-expressions-and-code-blocks

``genshi.max_cache_size``
-------------------------
The maximum number of templates that the template loader will cache in memory.
The default value is **25**. You may want to choose a higher value if your web
site uses a larger number of templates, and you have enough memory to spare.

``genshi.new_text_syntax``
--------------------------
Whether the new syntax for text templates should be used. Specify "yes" to
enable the new syntax, or "no" to use the old syntax.

In the version of Genshi, the default is to use the old syntax for
backwards-compatibility, but that will change in a future release.

.. _`search path`:

``genshi.search_path``
----------------------
A colon-separated list of file-system path names that the template loader should
use to search for templates.
