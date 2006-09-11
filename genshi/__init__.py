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

"""This package provides various means for generating and processing web markup
(XML or HTML).

The design is centered around the concept of streams of markup events (similar
in concept to SAX parsing events) which can be processed in a uniform manner
independently of where or how they are produced.


Generating content
------------------

Literal XML and HTML text can be used to easily produce markup streams
via helper functions in the `genshi.input` module:

>>> from genshi.input import XML
>>> doc = XML('<html lang="en"><head><title>My document</title></head></html>')

This results in a `Stream` object that can be used in a number of way.

>>> doc.render(method='html', encoding='utf-8')
'<html lang="en"><head><title>My document</title></head></html>'

>>> from genshi.input import HTML
>>> doc = HTML('<HTML lang=en><HEAD><TITLE>My document</HTML>')
>>> doc.render(method='html', encoding='utf-8')
'<html lang="en"><head><title>My document</title></head></html>'

>>> title = doc.select('head/title')
>>> title.render(method='html', encoding='utf-8')
'<title>My document</title>'


Markup streams can also be generated programmatically using the
`genshi.builder` module:

>>> from genshi.builder import tag
>>> doc = tag.doc(tag.title('My document'), lang='en')
>>> doc.generate().render(method='html')
'<doc lang="en"><title>My document</title></doc>'
"""

from genshi.core import *
from genshi.input import ParseError, XML, HTML
