# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.

from markup.core import Attributes, Namespace, QName, Stream

__all__ = ['Fragment', 'Element', 'tag']


class Fragment(object):
    __slots__ = ['children']

    def __init__(self):
        self.children = []

    def append(self, node):
        """Append an element or string as child node."""
        if isinstance(node, (Element, basestring, int, float, long)):
            # For objects of a known/primitive type, we avoid the check for
            # whether it is iterable for better performance
            self.children.append(node)
        elif isinstance(node, Fragment):
            self.children += node.children
        elif node is not None:
            try:
                children = iter(node)
            except TypeError:
                self.children.append(node)
            else:
                for child in node:
                    self.append(children)

    def __add__(self, other):
        return Fragment()(self, other)

    def __call__(self, *args):
        for arg in args:
            self.append(arg)
        return self

    def generate(self):
        """Generator that yield tags and text nodes as strings."""
        def _generate():
            for child in self.children:
                if isinstance(child, Fragment):
                    for event in child.generate():
                        yield event
                else:
                    yield Stream.TEXT, unicode(child), (-1, -1)
        return Stream(_generate())

    def __iter__(self):
        return iter(self.generate())

    def __str__(self):
        return str(self.generate())

    def __unicode__(self):
        return unicode(self.generate())


class Element(Fragment):
    """Simple XML output generator based on the builder pattern.

    Construct XML elements by passing the tag name to the constructor:

    >>> print Element('strong')
    <strong/>

    Attributes can be specified using keyword arguments. The values of the
    arguments will be converted to strings and any special XML characters
    escaped:

    >>> print Element('textarea', rows=10, cols=60)
    <textarea rows="10" cols="60"/>
    >>> print Element('span', title='1 < 2')
    <span title="1 &lt; 2"/>
    >>> print Element('span', title='"baz"')
    <span title="&#34;baz&#34;"/>

    The " character is escaped using a numerical entity.
    The order in which attributes are rendered is undefined.

    If an attribute value evaluates to `None`, that attribute is not included
    in the output:

    >>> print Element('a', name=None)
    <a/>

    Attribute names that conflict with Python keywords can be specified by
    appending an underscore:

    >>> print Element('div', class_='warning')
    <div class="warning"/>

    Nested elements can be added to an element using item access notation.
    The call notation can also be used for this and for adding attributes
    using keyword arguments, as one would do in the constructor.

    >>> print Element('ul')(Element('li'), Element('li'))
    <ul><li/><li/></ul>
    >>> print Element('a')('Label')
    <a>Label</a>
    >>> print Element('a')('Label', href="target")
    <a href="target">Label</a>

    Text nodes can be nested in an element by adding strings instead of
    elements. Any special characters in the strings are escaped automatically:

    >>> print Element('em')('Hello world')
    <em>Hello world</em>
    >>> print Element('em')(42)
    <em>42</em>
    >>> print Element('em')('1 < 2')
    <em>1 &lt; 2</em>

    This technique also allows mixed content:

    >>> print Element('p')('Hello ', Element('b')('world'))
    <p>Hello <b>world</b></p>

    Elements can also be combined with other elements or strings using the
    addition operator, which results in a `Fragment` object that contains the
    operands:
    
    >>> print Element('br') + 'some text' + Element('br')
    <br/>some text<br/>
    
    Elements with a namespace can be generated using the `Namespace` and/or
    `QName` classes:
    
    >>> from markup.core import Namespace
    >>> xhtml = Namespace('http://www.w3.org/1999/xhtml')
    >>> print Element(xhtml.html, lang='en')
    <html lang="en" xmlns="http://www.w3.org/1999/xhtml"/>
    """
    __slots__ = ['tag', 'attrib']

    def __init__(self, tag_, **attrib):
        Fragment.__init__(self)
        self.tag = QName(tag_)
        self.attrib = Attributes()
        self(**attrib)

    def __call__(self, *args, **kwargs):
        for attr, value in kwargs.items():
            if value is None:
                continue
            attr = attr.rstrip('_').replace('_', '-')
            self.attrib.set(attr, value)
        return Fragment.__call__(self, *args)

    def generate(self):
        """Generator that yield tags and text nodes as strings."""
        def _generate():
            yield Stream.START, (self.tag, self.attrib), (-1, -1)
            for kind, data, pos in Fragment.generate(self):
                yield kind, data, pos
            yield Stream.END, self.tag, (-1, -1)
        return Stream(_generate())


class ElementFactory(object):

    def __init__(self, namespace=None):
        if namespace and not isinstance(namespace, Namespace):
            namespace = Namespace(namespace)
        self.namespace = namespace

    def __getitem__(self, namespace):
        return ElementFactory(namespace)

    def __getattr__(self, name):
        return Element(self.namespace and self.namespace[name] or name)


tag = ElementFactory()
