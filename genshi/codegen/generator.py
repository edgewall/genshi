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


from genshi import template
from genshi.template import Template
from genshi.codegen.printer import PythonPrinter, PYTHON_LINE, PYTHON_COMMENT, PYTHON_BLOCK

_directive_printers = {}
        
class DirectivePrinter(object):
    def __init__(self):
        _directive_printers[self.__directive__] = self
    def start_directive(self, gencontext, directive):
        pass
    def end_directive(self, gencontext, directive):
        pass
        
class ForDirectivePrinter(DirectivePrinter):
    __directive__ = template.ForDirective
    def start_directive(self, gencontext, directive):
        x = {}
        directive.assign(x, None)
        varname = list(x)[0]
        yield (PYTHON_LINE, "for %s in %s:" % (varname, directive.expr.source))
    def end_directive(self, gencontext, directive):
        yield (PYTHON_LINE, "")
ForDirectivePrinter()

class Generator(object):
    """given a Template, generates Python modules (as strings or code objects)
    optimized to a particular Serializer."""
    def __init__(self, template):
        self.template = template
    def generate(self, serializer):
        return PythonPrinter(
            PythonGenerator(
                self.template.stream, serializer
            ).generate()
        ).generate()

class PythonGenerator(object):
    def __init__(self, stream, serializer):
        self.stream = stream
        self.serializer = serializer
    def generate(self):
        for evt in self.start():
            yield evt
        for evt in self.gen_stream(self.stream):
            yield evt
        for  evt in self.end():
            yield evt

    def gen_stream(self, stream):
        for event in self.serializer(stream):
            (kind, data, pos, literal) = event
            if kind is template.SUB:
                directives, substream = event[1]
                for d in directives:
                    for evt in self.produce_directive_start(d):
                        yield evt
                for evt in self.gen_stream(substream):
                    yield evt
                for d in directives:
                    for evt in self.produce_directive_end(d):
                        yield evt
            elif kind is template.START:
                for evt in self.produce_start_event(event):
                    yield evt
            elif kind is template.END:
                for evt in self.produce_end_event(event):
                    yield evt
    def produce_preamble(self):
        for line in [
            "from genshi.core import START, END, START_NS, END_NS, TEXT, COMMENT, DOCTYPE, QName, Stream",
            "from genshi.template import Context",
            "from genshi.path import Path"
        ]:
            yield (PYTHON_LINE, line)

    def produce_directive_start(self, directive):
        for evt in _directive_printers[directive.__class__].start_directive(self, directive):
            yield evt
    def produce_directive_end(self, directive):
        for evt in _directive_printers[directive.__class__].end_directive(self, directive):
            yield evt
    def start(self):
        for evt in self.produce_preamble():
            yield evt
        yield (PYTHON_LINE, "def go(context):")
    def end(self):
        yield (PYTHON_LINE, "")
    def produce_start_event(self, event):
        yield (PYTHON_LINE, "yield (START, (Qname(%s), %s), %s, %s)" % (
            repr(event[1][0]), 
            repr(event[1][1]), 
            repr(event[2]), 
            repr(event[3]))
        )
    def produce_end_event(self, event):
        yield (PYTHON_LINE, "yield (END, (%s), %s, %s)" % (
            repr(event[1]), 
            repr(event[2]), 
            repr(event[3]))
        )



