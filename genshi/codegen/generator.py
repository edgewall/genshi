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
from genshi.template import Template, Context
from genshi.path import Path
from genshi.core import QName
from genshi.codegen.printer import PythonPrinter, PYTHON_LINE, PYTHON_COMMENT, PYTHON_BLOCK
from genshi.codegen import serialize, adapters, output
from compiler import ast, parse, visitor
import sets, re

_directive_printers = {}

def _ident_from_assign(assign):
    # a little trick to get the variable name from the already 
    # compiled assignment expression
    x = {}
    assign(x, None)
    return list(x)[0]
    
class DirectivePrinter(object):
    def __init__(self):
        _directive_printers[self.__directive__] = self
    def produce_directive(self, gencontext, directive, event, substream):
        pass
    def declared_identifiers(self, gencontext, directive, event):
        return []
    def undeclared_identifiers(self, gencontext, directive, event):
        return []
                
class ForDirectivePrinter(DirectivePrinter):
    __directive__ = template.ForDirective
    def produce_directive(self, gencontext, directive, event, substream):
        varname = _ident_from_assign(directive.assign)
        yield (PYTHON_LINE, "for %s in %s:" % (varname, directive.expr.source))
        for evt in gencontext.gen_stream(substream):
            yield evt
        yield (PYTHON_LINE, "")
    def declared_identifiers(self, gencontext, directive, event):
        return [_ident_from_assign(directive.assign)]
    def undeclared_identifiers(self, gencontext, directive, event):
        s = _SearchIdents(directive.expr.source)
        return list(s.identifiers)
ForDirectivePrinter()

class IfDirectivePrinter(DirectivePrinter):
    __directive__ = template.IfDirective
    def produce_directive(self, gencontext, directive, event, substream):
        yield (PYTHON_LINE, "if %s:" % (directive.expr.source))
        for evt in gencontext.gen_stream(substream):
            yield evt
        yield (PYTHON_LINE, "")
IfDirectivePrinter()

class ReplaceDirectivePrinter(DirectivePrinter):
    __directive__ = template.ReplaceDirective
    def produce_directive(self, gencontext, directive, event, substream):
        for expr in gencontext.produce_expr_event(event, directive.expr):
            yield expr
ReplaceDirectivePrinter()

class DefDirectivePrinter(DirectivePrinter):
    __directive__ = template.DefDirective
    def produce_directive(self, gencontext, directive, event, substream):
        sig = directive.signature
        gencontext.defs.add(directive.name)
        if not re.search(r'\(.*\)$', sig):
            gencontext.defs_without_params.add(sig)
            sig += '()'
        yield (PYTHON_LINE, "def %s:" % (sig))
        for evt in gencontext.gen_stream(substream):
            yield evt
        yield (PYTHON_LINE, "")
    def declared_identifiers(self, gencontext, directive, event):
        return [directive.name] + directive.args + directive.defaults.keys()
    def undeclared_identifiers(self, gencontext, directive, event):
        result = sets.Set()
        for expr in directive.defaults.values():
            s = _SearchIdents(expr.node)
            result = result.union(s.identifiers)
        return iter(result)
DefDirectivePrinter()

class Generator(object):
    """given a Template, generates Python modules (as strings or code objects)
    optimized to a particular Serializer."""
    def __init__(self, template, method='html', serializer=None, strip_whitespace=False, filters=None):
        self.template = template
        self.serializer = serializer or ({
                'xml':   serialize.XMLSerializeFilter,
               'xhtml': serialize.XHTMLSerializeFilter,
               'html':  serialize.HTMLSerializeFilter,
               'text':  serialize.TextSerializeFilter}[method]())
        self.code = self._generate_module()
        self.filters = filters or []
        if strip_whitespace:
            self.filters.append(output.PostWhitespaceFilter())
    def generate(self, *args, **kwargs):
        if args:
            assert len(args) == 1
            ctxt = args[0]
            if ctxt is None:
                ctxt = Context(**kwargs)
            assert isinstance(ctxt, Context)
        else:
            ctxt = Context(**kwargs)
        
        return adapters.InlineStream(self, ctxt)
        
    def _generate_code_events(self):
        return PythonPrinter(
            PythonGenerator(
                self.template.stream, self.serializer
            ).generate()
        ).generate()
    def _generate_module(self):
        import imp
        module = imp.new_module("_some_ident")
        pycode = u''.join(self._generate_code_events())
        code = compile(pycode, '<String>', 'exec')
        exec code in module.__dict__, module.__dict__
        return module
            
class _SearchIdents(visitor.ASTVisitor):
    """an ASTVisitor that can locate identifier names in a string-based code block.

    This is not used in this example module, but will be used to locate and pre-declare 
    all identifiers that are referenced in expressions at the start of each generated callable."""
    def __init__(self, expr):
        self.identifiers = sets.Set()
        if isinstance(expr, basestring):
            expr = parse(expr, "eval")
        visitor.walk(expr, self)
    def visitName(self, node, *args, **kwargs):
        self.identifiers.add(node.name)

class PythonGenerator(object):
    def __init__(self, stream, serializer):
        self.stream = stream
        self.serializer = serializer
        self.defs_without_params = sets.Set()
        self.defs = sets.Set()
    def generate(self):
        for evt in self.start():
            yield evt
        stream = list(self.stream)
        for expr in self.find_identifiers(stream, sets.ImmutableSet()):
            yield expr
        for evt in self.gen_stream(stream):
            yield evt
        for  evt in self.end():
            yield evt

    def find_identifiers(self, stream, stack):
        """locate undeclared python identifiers in the given stream.  stack is an empty set."""
        for evt in stream:
            if evt[0] is template.EXPR:
                s = _SearchIdents(evt[1].source)
                for ident in s.identifiers.difference(stack):
                    yield (PYTHON_LINE, "%s = context.get('%s', None)" % (ident, ident))
            elif evt[0] is template.SUB:
                directives, substream = evt[1]
                decl_ident = []
                for d in directives:
                    decl_ident += self.get_declared_identifiers(d, evt[1][1])
                    for ident in self.get_undeclared_identifiers(d, evt[1][1]):
                        yield (PYTHON_LINE, "%s = context.get('%s', None)" % (ident, ident))
                stack = stack.union(sets.Set(decl_ident))
                for evt in self.find_identifiers(evt[1][1], stack):
                    yield evt
                
    def gen_stream(self, stream):
        for event in self.serializer(stream):
            (kind, data, pos, literal) = event
            if kind is template.SUB:
                directives, substream = event[1]
                for d in directives:
                    for evt in self.produce_directive(d, event, substream):
                        yield evt
            elif kind is template.START:
                for evt in self.produce_start_event(event):
                    yield evt
            elif kind is template.END:
                for evt in self.produce_end_event(event):
                    yield evt
            elif kind is template.EXPR:
                for evt in self.produce_expr_event(event):
                    yield evt
            elif kind is template.TEXT:
                for evt in self.produce_text_event(event):
                    yield evt
    def produce_preamble(self):
        for line in [
            "from genshi.core import START, END, START_NS, END_NS, TEXT, COMMENT, DOCTYPE, Stream",
            "from genshi.template import Context, Template",
            "from genshi.path import Path",
            "from genshi.codegen import interp",
            "EXPR = Template.EXPR"
        ]:
            yield (PYTHON_LINE, line)
    def get_declared_identifiers(self, directive, event):
        return _directive_printers[directive.__class__].declared_identifiers(self, directive, event)
    def get_undeclared_identifiers(self, directive, event):
        return _directive_printers[directive.__class__].undeclared_identifiers(self, directive, event)
    def produce_directive(self, directive, event, substream):
        for evt in _directive_printers[directive.__class__].produce_directive(self, directive, event, substream):
            yield evt
    def start(self):
        for evt in self.produce_preamble():
            yield evt
        yield (PYTHON_LINE, "def go(context):")
    def end(self):
        yield (PYTHON_LINE, "")
    def produce_start_event(self, event):
        qn = QName(event[1][0])
        yield (PYTHON_LINE, "yield (START, (%s, %s, %s), %s, %s)" % (
            repr(qn.namespace),
            repr(qn.localname), 
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
    def produce_expr_event(self, event, expr=None):
        if expr is None:
            expr = event[1]
        if expr.source in self.defs_without_params:
            yield (PYTHON_LINE, "for _evt in interp.evaluate(%s(), %s):" % (expr.source, repr(event[2])))
        else:
            yield (PYTHON_LINE, "for _evt in interp.evaluate(%s, %s):" % (expr.source, repr(event[2])))
        yield (PYTHON_LINE, "yield _evt")
        yield (PYTHON_LINE, "")
        
    def produce_text_event(self, event):
        yield (PYTHON_LINE, "yield (TEXT, (%s), %s, %s)" % (
            repr(unicode(event[1])),
            repr(event[2]),
            repr(unicode(event[3]))
        ))

