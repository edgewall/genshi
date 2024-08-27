.. -*- mode: rst; encoding: utf-8 -*-

=================
Loading Templates
=================

Genshi comes with a simple but flexible implementation of a template loader in
the ``genshi.template.loader`` module. The loader provides caching of
templates so they do not need to be reparsed when used, support for multiple
template directories that together form a virtual search path, as well as
support for different template loading strategies.


-----
Usage
-----

The basic usage pattern is simple: instantiate one ``TemplateLoader`` object
and keep it around, then ask it to load a template whenever you need to load
one:

.. code-block:: python

  from genshi.template import TemplateLoader
  
  loader = TemplateLoader(['/path/to/dir1', '/path/to/dir2'],
                          auto_reload=True)
  tmpl = loader.load('test.html')

When you try to load a template that can't be found, you get a
``TemplateNotFound`` error.

The default template class used by the loader is ``MarkupTemplate``, but that
can be overridden both with a different default (as a keyword argument to the
``TemplateLoader`` constructor), as well as on invocation of the ``load()``
method:

.. code-block:: python

  from genshi.template.text import NewTextTemplate
  
  tmpl = loader.load('mail.txt', cls=NewTextTemplate)


-------
Caching
-------

The ``TemplateLoader`` class provides a simple in-memory cache for parsed
template objects. This improves performance, because templates do not need to
be reparsed every time they are rendered.

The size of this cache can be adjusted using the `max_cache_size` option on
the ``TemplateLoader`` constructor. The value of that option determines the
maximum number of template objects kept in the cache. When this limit is
reached, any templates that haven't been used in a while get purged.
Technically, this is a least-recently-used (LRU) cache, the default limit is
set to 25 templates.

Automatic Reloading
===================

Once a template has been cached, it will normally not get reparsed until it
has been purged from the cache. This means that any changes to the template
file are not taken into consideration as long as it is still found in the
cache. As this is inconvenient in development scenarios, the ``auto_reload``
option allows for automatic cache invalidation based on whether the template
source has changed.

.. code-block:: python

  from genshi.template import TemplateLoader
  
  loader = TemplateLoader('templates', auto_reload=True, max_cache_size=100)

In production environments, automatic reloading should be disabled, as it does
affect performance negatively.

Callback Interface
==================

Sometimes you need to make sure that templates get properly configured after
they have been loaded, but you only want to do that when the template is
actually loaded and parsed, not when it is returned from the cache.

For such cases, the ``TemplateLoader`` provides a way to specify a callback
function that gets invoked whenever a template is loaded. You can specify that
callback by passing it into the loader constructor via the ``callback``
keyword argument, or later by setting the attribute of the same name. The
callback function should expect a single argument, the template object.

For example, to properly inject the `translation filter`_ into any loaded
template, you'd use code similar to this:

.. code-block:: python

  from genshi.filters import Translator
  from genshi.template import TemplateLoader
  
  def template_loaded(template):
      Translator(translations.ugettext).setup(template)
  
  loader = TemplateLoader('templates', callback=template_loaded)

.. _`translation filter`: i18n.html

--------------------
Template Search Path
--------------------

The template loader can be configured with a list of multiple directories to
search for templates. The loader maps these directories to a single logical
directory for locating templates by file name.

The order of the directories making up the search path is significant: the
loader will first try to locate a requested template in the first directory on
the path, then in the second, and so on. If there are two templates with the
same file name in multiple directories on the search path, whatever file is
found first gets used.

Based on this design, an application could, for example, configure a search
path consisting of a directory containing the default templates, as well as a
directory where site-specific templates can be stored that will override the
default templates.


Load Functions
==============

Usually the search path consists of strings representing directory paths, but
it may also contain “load functions”: functions that are basically invoked
with the file name, and return the template content.

Genshi comes with three builtin load functions:

``directory(path)``
-------------------

The equivalent of just using a string containing the directory path: looks up
the file name in a specific directory.

.. code-block:: python

  from genshi.template import TemplateLoader, loader
  tl = TemplateLoader([loader.directory('/path/to/dir/')])

That is the same as:

.. code-block:: python

  tl = TemplateLoader(['/path/to/dir/'])


``package(name, path)``
-----------------------

Uses the ``pkg_resources`` API to locate files in Python package data (which
may be inside a ZIP archive).

.. code-block:: python

  from genshi.template import TemplateLoader, loader
  tl = TemplateLoader([loader.package('myapp', 'templates')])

This will look for templates in the ``templates`` directory of the Python
package ``myapp``.

``prefixed(**delegates)``
-------------------------

Delegates load requests to different load functions based on the path prefix.

.. code-block:: python

  from genshi.template import TemplateLoader, loader
  tl = TemplateLoader(loader.prefixed(
    core = '/tmp/dir1',
    plugin1 = loader.package('plugin1', 'templates'),
    plugin2 = loader.package('plugin2', 'templates'),
  ))
  tmpl = tl.load('core/index.html')

This example sets up a loader with three delegates, under the prefixes “core”,
“plugin1”, and “plugin2”. When a template is requested, the ``prefixed`` load
function looks for a delegate with a corresponding prefix, removes the prefix
from the path and asks the delegate to load the template.

In this case, assuming the directory ``/path/to/dir`` contains a file named
``index.html``, that file will be used when we load ``core/index.html``. The
other delegates are not checked as their prefix does not match.


.. note:: These builtin load functions are available both as class methods
          of the ``TemplateLoader`` class as well as on the module level


Custom Load Functions
---------------------

You can easily use your own load function with the template loader, for
example to load templates from a database. All that is needed is a callable
object that accepts a ``filename`` (a string) and returns a tuple of the form
``(filepath, filename, fileobj, uptodate_fun)``, where:

``filepath``
  is the absolute path to the template. This is primarily used for output in
  tracebacks, and does not need to map to an actual path on the file system.
``filename``
  is the base name of the template file
``fileobj``
  is a readable file-like object that provides the content of the template
``uptodate_fun``
  is a function that the loader can invoke to check whether the cached version
  of the template is still up-to-date, or ``None`` if the load function is not
  able to provide such a check. If provided, the function should not expect
  any parameters (so you'll definitely want to use a closure here), and should
  return ``True`` if the template has not changed since it was last loaded.

When the requested template can not be found, the function should raise an
``IOError`` or ``TemplateNotFound`` exception.


------------------
Customized Loading
------------------

If you require a completely different implementation of template loading, you
can extend or even replace the builtin ``TemplateLoader`` class.

Protocol
========

The protocol between the template loader and the ``Template`` class is simple
and only used for processing includes. The only required part of that protocol
is that the object assigned to ``Template.loader`` implements a ``load``
method compatible to that of the ``TemplateLoader`` class, at the minimum with
the signature ``load(filename, relative_to=None, cls=None)``.

In addition, templates currently check for the existence and value of a boolean
``auto_reload`` property. If the property does not exist or evaluates to a
non-truth value, inlining of included templates is disabled. Inlining is a
small optimization that removes some overhead in the processing of includes.

Subclassing ``TemplateLoader``
==============================

You can also adjust the behavior of the ``TemplateLoader`` class by subclassing
it. You can of course override anything needed, but the class also provides the
``_instantiate()`` hook, which is intended for use by subclasses to customize
the creation of the template object from the file name and content. Please
consult the code and the API documentation for more detail.
