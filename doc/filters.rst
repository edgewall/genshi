.. -*- mode: rst; encoding: utf-8 -*-

==============
Stream Filters
==============

:doc:`streams` showed how to write filters and how they are applied to
markup streams. This page describes the features of the various filters that
come with Genshi itself.


.. _HTMLFormFiller:

HTML Form Filler
================

The filter ``genshi.filters.html.HTMLFormFiller`` can automatically populate an
HTML form from values provided as a simple dictionary. When using this filter,
you can basically omit any ``value``, ``selected``, or ``checked`` attributes
from form controls in your templates, and let the filter do all that work for
you.

``HTMLFormFiller`` takes a dictionary of data to populate the form with, where
the keys should match the names of form elements, and the values determine the
values of those controls. For example:

.. code-block:: pycon

  >>> from genshi.filters import HTMLFormFiller
  >>> from genshi.template import MarkupTemplate
  
  >>> template = MarkupTemplate("""<form>
  ...   <p>
  ...     <label>User name:
  ...       <input type="text" name="username" />
  ...     </label><br />
  ...     <label>Password:
  ...       <input type="password" name="password" />
  ...     </label><br />
  ...     <label>
  ...       <input type="checkbox" name="remember" /> Remember me
  ...     </label>
  ...   </p>
  ... </form>""")
  >>> filler = HTMLFormFiller(data=dict(username='john', remember=True))
  >>> print(template.generate() | filler)
  <form>
    <p>
      <label>User name:
        <input type="text" name="username" value="john"/>
      </label><br/>
      <label>Password:
        <input type="password" name="password"/>
      </label><br/>
      <label>
        <input type="checkbox" name="remember" checked="checked"/> Remember me
      </label>
    </p>
  </form>

.. note:: This processing is done without in any way reparsing the template
          output. As any stream filter it operates after the template output is
          generated but *before* that output is actually serialized.

The filter will of course also handle radio buttons as well as ``<select>`` and
``<textarea>`` elements. For radio buttons to be marked as checked, the value in
the data dictionary needs to match the ``value`` attribute of the ``<input>``
element, or evaluate to a truth value if the element has no such attribute. For
options in a ``<select>`` box to be marked as selected, the value in the data
dictionary needs to match the ``value`` attribute of the ``<option>`` element,
or the text content of the option if it has no ``value`` attribute. Password and
file input fields are not populated, as most browsers would ignore that anyway
for security reasons.

You'll want to make sure that the values in the data dictionary have already
been converted to strings. While the filter may be able to deal with non-string
data in some cases (such as check boxes), in most cases it will either not
attempt any conversion or not produce the desired results.

You can restrict the form filler to operate only on a specific ``<form>`` by
passing either the ``id`` or the ``name`` keyword argument to the initializer.
If either of those is specified, the filter will only apply to form tags with
an attribute matching the specified value.


HTML Sanitizer
==============

The filter ``genshi.filters.html.HTMLSanitizer`` filter can be used to clean up
user-submitted HTML markup, removing potentially dangerous constructs that could
be used for various kinds of abuse, such as cross-site scripting (XSS) attacks:

.. code-block:: pycon

  >>> from genshi.filters import HTMLSanitizer
  >>> from genshi.input import HTML
  
  >>> html = HTML(u"""<div>
  ...   <p>Innocent looking text.</p>
  ...   <script>alert("Danger: " + document.cookie)</script>
  ... </div>""")
  >>> sanitize = HTMLSanitizer()
  >>> print(html | sanitize)
  <div>
    <p>Innocent looking text.</p>
  </div>

In this example, the ``<script>`` tag was removed from the output.

You can determine which tags and attributes should be allowed by initializing
the filter with corresponding sets. See the API documentation for more
information.

Inline ``style`` attributes are forbidden by default. If you allow them, the
filter will still perform sanitization on the contents any encountered inline
styles: the proprietary ``expression()`` function (supported only by Internet
Explorer) is removed, and any property using an ``url()`` which a potentially
dangerous URL scheme (such as ``javascript:``) are also stripped out:

.. code-block:: pycon

  >>> from genshi.filters import HTMLSanitizer
  >>> from genshi.input import HTML
  
  >>> html = HTML(u"""<div>
  ...   <br style="background: url(javascript:alert(document.cookie); color: #000" />
  ... </div>""")
  >>> sanitize = HTMLSanitizer(safe_attrs=HTMLSanitizer.SAFE_ATTRS | set(['style']))
  >>> print(html | sanitize)
  <div>
    <br style="color: #000"/>
  </div>

.. warning:: You should probably not rely on the ``style`` filtering, as
             sanitizing mixed HTML, CSS, and Javascript is very complicated and
             suspect to various browser bugs. If you can somehow get away with
             not allowing inline styles in user-submitted content, that would
             definitely be the safer route to follow.


Transformer
===========

The filter ``genshi.filters.transform.Transformer`` provides a convenient way to
transform or otherwise work with markup event streams. It allows you to specify
which parts of the stream you're interested in with XPath expressions, and then
attach a variety of transformations to the parts that match:

.. code-block:: pycon

  >>> from genshi.builder import tag
  >>> from genshi.core import TEXT
  >>> from genshi.filters import Transformer
  >>> from genshi.input import HTML
  
  >>> html = HTML(u'''<html>
  ...   <head><title>Some Title</title></head>
  ...   <body>
  ...     Some <em>body</em> text.
  ...   </body>
  ... </html>''')
  
  >>> print(html | Transformer('body/em').map(unicode.upper, TEXT)
  ...                                    .unwrap().wrap(tag.u).end()
  ...                                    .select('body/u')
  ...                                    .prepend('underlined '))
  <html>
    <head><title>Some Title</title></head>
    <body>
      Some <u>underlined BODY</u> text.
    </body>
  </html>

This example sets up a transformation that:

 1. matches any `<em>` element anywhere in the body,
 2. uppercases any text nodes in the element,
 3. strips off the `<em>` start and close tags,
 4. wraps the content in a `<u>` tag, and
 5. inserts the text `underlined` inside the `<u>` tag.

A number of commonly useful transformations are available for this filter.
Please consult the API documentation a complete list.

In addition, you can also perform custom transformations. For example, the
following defines a transformation that changes the name of a tag:

.. code-block:: pycon

  >>> from genshi import QName
  >>> from genshi.filters.transform import ENTER, EXIT
  
  >>> class RenameTransformation(object):
  ...    def __init__(self, name):
  ...        self.name = QName(name)
  ...    def __call__(self, stream):
  ...        for mark, (kind, data, pos) in stream:
  ...            if mark is ENTER:
  ...                data = self.name, data[1]
  ...            elif mark is EXIT:
  ...                data = self.name
  ...            yield mark, (kind, data, pos)

A transformation can be any callable object that accepts an augmented event
stream. In this case we define a class, so that we can initialize it with the
tag name.

Custom transformations can be applied using the `apply()` method of a
transformer instance:

.. code-block:: pycon

  >>> xform = Transformer('body//em').map(unicode.upper, TEXT) \
  >>> xform = xform.apply(RenameTransformation('u'))
  >>> print(html | xform)
  <html>
    <head><title>Some Title</title></head>
    <body>
      Some <u>BODY</u> text.
    </body>
  </html>

.. note:: The transformation filter was added in Genshi 0.5.


Translator
==========

The ``genshi.filters.i18n.Translator`` filter implements basic support for
internationalizing and localizing templates. When used as a filter, it
translates a configurable set of text nodes and attribute values using a
``gettext``-style translation function.

The ``Translator`` class also defines the ``extract`` class method, which can
be used to extract localizable messages from a template.

Please refer to the API documentation for more information on this filter.

.. note:: The translation filter was added in Genshi 0.4.
