# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

from genshi.core import Attrs, Namespace, QName, Stream, START, END, TEXT

__all__ = ['Fragment', 'Element', 'tag']


class Fragment(object):
    """Represents a markup fragment, which is basically just a list of element
    or text nodes.
    """
    __slots__ = ['children']

    def __init__(self):
        self.children = []

    def __add__(self, other):
        return Fragment()(self, other)

    def __call__(self, *args):
        map(self.append, args)
        return self

    def __iter__(self):
        return self._generate()

    def __repr__(self):
        return '<%s>' % self.__class__.__name__

    def __str__(self):
        return str(self.generate())

    def __unicode__(self):
        return unicode(self.generate())

    def append(self, node):
        """Append an element or string as child node."""
        if isinstance(node, (Element, basestring, int, float, long)):
            # For objects of a known/primitive type, we avoid the check for
            # whether it is iterable for better performance
            self.children.append(node)
        elif isinstance(node, Fragment):
            self.children.extend(node.children)
        elif node is not None:
            try:
                map(self.append, iter(node))
            except TypeError:
                self.children.append(node)

    def _generate(self):
        for child in self.children:
            if isinstance(child, Fragment):
                for event in child._generate():
                    yield event
            else:
                if not isinstance(child, basestring):
                    child = unicode(child)
                yield TEXT, child, (None, -1, -1)

    def generate(self):
        """Return a markup event stream for the fragment."""
        return Stream(self._generate())


def _value_to_unicode(value):
    if isinstance(value, unicode):
        return value
    return unicode(value)

def _kwargs_to_attrs(kwargs):
    return [(k.rstrip('_').replace('_', '-'), _value_to_unicode(v))
            for k, v in kwargs.items() if v is not None]


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

    Quotes are not escaped inside text nodes:
    >>> print Element('p')('"Hello"')
    <p>"Hello"</p>

    Elements can also be combined with other elements or strings using the
    addition operator, which results in a `Fragment` object that contains the
    operands:
    
    >>> print Element('br') + 'some text' + Element('br')
    <br/>some text<br/>
    
    Elements with a namespace can be generated using the `Namespace` and/or
    `QName` classes:
    
    >>> from genshi.core import Namespace
    >>> xhtml = Namespace('http://www.w3.org/1999/xhtml')
    >>> print Element(xhtml.html, lang='en')
    <html lang="en" xmlns="http://www.w3.org/1999/xhtml"/>
    """
    __slots__ = ['tag', 'attrib']

    def __init__(self, tag_, **attrib):
        Fragment.__init__(self)
        self.tag = QName(tag_)
        self.attrib = Attrs(_kwargs_to_attrs(attrib))

    def __call__(self, *args, **kwargs):
        self.attrib |= Attrs(_kwargs_to_attrs(kwargs))
        Fragment.__call__(self, *args)
        return self

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.tag)

    def _generate(self):
        yield START, (self.tag, self.attrib), (None, -1, -1)
        for kind, data, pos in Fragment._generate(self):
            yield kind, data, pos
        yield END, self.tag, (None, -1, -1)

    def generate(self):
        """Return a markup event stream for the fragment."""
        return Stream(self._generate())


class ElementFactory(object):
    """Factory for `Element` objects.
    
    A new element is created simply by accessing a correspondingly named
    attribute of the factory object:
    
    >>> factory = ElementFactory()
    >>> print factory.foo
    <foo/>
    >>> print factory.foo(id=2)
    <foo id="2"/>
    
    Markup fragments (lists of nodes without a parent element) can be created
    by calling the factory:
    
    >>> print factory('Hello, ', factory.em('world'), '!')
    Hello, <em>world</em>!
    
    A factory can also be bound to a specific namespace:
    
    >>> factory = ElementFactory('http://www.w3.org/1999/xhtml')
    >>> print factory.html(lang="en")
    <html lang="en" xmlns="http://www.w3.org/1999/xhtml"/>
    
    The namespace for a specific element can be altered on an existing factory
    by specifying the new namespace using item access:
    
    >>> factory = ElementFactory()
    >>> print factory.html(factory['http://www.w3.org/2000/svg'].g(id=3))
    <html><g id="3" xmlns="http://www.w3.org/2000/svg"/></html>
    
    Usually, the `ElementFactory` class is not be used directly. Rather, the
    `tag` instance should be used to create elements.
    """

    def __init__(self, namespace=None):
        """Create the factory, optionally bound to the given namespace.
        
        @param namespace: the namespace URI for any created elements, or `None`
            for no namespace
        """
        if namespace and not isinstance(namespace, Namespace):
            namespace = Namespace(namespace)
        self.namespace = namespace

    def __call__(self, *args):
        return Fragment()(*args)

    def __getitem__(self, namespace):
        """Return a new factory that is bound to the specified namespace."""
        return ElementFactory(namespace)

    def __getattr__(self, name):
        """Create an `Element` with the given name."""
        return Element(self.namespace and self.namespace[name] or name)


tag = ElementFactory()
