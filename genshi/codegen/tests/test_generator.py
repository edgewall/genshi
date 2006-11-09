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
from genshi.output import XMLSerializer
from genshi.codegen import generator, interp
import time, sys

text = """<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:py="http://genshi.edgewall.org/"
      xmlns:xi="http://www.w3.org/2001/XInclude"
      lang="en">
 <body>
 <py:match path='*[@class="message"]'>
     matched the message, which was ${select('*|text()')}
     </py:match>

        
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

data = {'lala':'hi', 'items':lambda:["one", "two", "three"], 'foo':['f1', 'f2', 'f3']}
    
t = MarkupTemplate(text)
#print t.generate(**data).render()
#sys.exit()

g = generator.Generator(t)
pycode =  u''.join(g._generate_code_events())
print pycode

print str(g.generate(**data))

#sys.exit()

print "Running MarkupTemplate.generate()/HTMLSerializer..."
now = time.time()
for x in range(1,1000):
    stream = t.generate(**data)
    stream.render()
print "MarkupTemplate.generate()/HTMLSerializer totaltime: %f" % (time.time() - now)

# inline
print "Running inlined module..."
now = time.time()
for x in range(1,1000):
    str(g.generate(**data))
print "Inlined module totaltime: %f" % (time.time() - now)

# inline with whitespace filter
print "Running inlined module..."
g = generator.Generator(t, strip_whitespace=True)
now = time.time()
for x in range(1,1000):
    str(g.generate(**data))

print "Inlined module w/ strip_whitespace totaltime: %f" % (time.time() - now)
