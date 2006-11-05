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

from genshi.template import MarkupTemplate, Template, Context
from genshi.output import HTMLSerializer
from genshi.codegen import generator, interp
from genshi.codegen.serialize import HTMLSerializeFilter
import time, sys

text = """<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:py="http://genshi.edgewall.org/"
      xmlns:xi="http://www.w3.org/2001/XInclude"
      lang="en">
 <body>
    <div py:for="item in items()">
        ${lala + 'hi'}
        <div py:for="x in foo">
        i am a greeting, ${item}, ${x}
        
        now heres replace
        <span py:replace="item">Hey Ho</span>
        </div>
    </div>

    <p py:def="echo(greeting, name='world', value=somecontextvalue)" class="message">
        ${greeting}, ${name}!
    </p>
    ${echo('Hi', name='you')}
    
    <p py:def="helloworld" class="message">
        Hello, world!
      </p>
    ${helloworld}
     yo
     <hi></hi>
 </body>
</html>"""

def items():
    return ["one", "two", "three"]

data = {'lala':'hi', 'items':items, 'foo':['f1', 'f2', 'f3']}
    
t = MarkupTemplate(text)
print u''.join(HTMLSerializer()(t.generate(**data)))

g = generator.Generator(t)
pycode =  u''.join(g.generate_stream(HTMLSerializeFilter()))
print pycode

g = generator.Generator(t)
module = g.generate_module(HTMLSerializeFilter())
print u''.join(interp.run_inlined(module, data))

print "Running MarkupTemplate.generate()/HTMLSerializer..."
now = time.time()
for x in range(1,1000):
    stream = t.generate(**data)
    serializer = HTMLSerializer()
    list(serializer(stream))
print "MarkupTemplate.generate()/HTMLSerializer totaltime: %f" % (time.time() - now)

# inline
print "Running inlined module..."
now = time.time()
for x in range(1,1000):
    list(interp.run_inlined(module, data))
print "Inlined module totaltime: %f" % (time.time() - now)
