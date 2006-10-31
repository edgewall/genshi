# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software and Michael Bayer <mike_mp@zzzcomputing.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

from genshi.template import MarkupTemplate, Template
from genshi.output import HTMLSerializer
from genshi.codegen import generator
from genshi.codegen.serialize import HTMLSerializeFilter

text = """<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:py="http://genshi.edgewall.org/"
      xmlns:xi="http://www.w3.org/2001/XInclude"
      lang="en">
 <body>
    <div py:for="item in items()">
        <div py:for="x in foo">
        i am a greeting, ${item}
        </div>
    </div>
    
     yo
     <hi></hi>
 </body>
</html>"""

t = MarkupTemplate(text)
g = generator.Generator(t)
print u''.join(g.generate(HTMLSerializeFilter()))
