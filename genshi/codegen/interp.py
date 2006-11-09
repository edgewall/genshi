"""defines resources available to generated modules"""

from genshi.template import MarkupTemplate, Template, Context
from genshi.path import Path
from genshi.output import HTMLSerializer
from genshi.codegen import adapters
from compiler import ast, parse, visitor
from genshi.core import START, END, START_NS, END_NS, TEXT, COMMENT, DOCTYPE, QName, Stream
EXPR = Template.EXPR
import sets
from itertools import chain

# we re-implement our own _match function, based on MarkupTemplate._match.
def _match(stream, ctxt, match_templates=None):
    """match method from MarkupTemplate, modified to handle inlined stream of events.
    
    comments from the original function in template.py are removed, to highlight new commentary
    unique to this method."""
    if match_templates is None:
        match_templates = ctxt._match_templates

    tail = []
    def _strip(stream):
        depth = 1
        while 1:
            event = stream.next()
            if event[0] is START:
                depth += 1
            elif event[0] is END:
                depth -= 1
            if depth > 0:
                yield event
            else:
                tail[:] = [event]
                break

    for event in stream:
#        print "TESTING EVENT", event
        if not match_templates or (event[0] is not START and
                                   event[0] is not END):
            yield event
            continue
        for idx, (test, path, template, namespaces) in \
                enumerate(match_templates):

            if test(event, namespaces, ctxt) is True:
                for test in [mt[0] for mt in match_templates[idx + 1:]]:
                    test(event, namespaces, ctxt, updateonly=True)
                    
                content = chain([event], _match(_strip(stream), ctxt),
                                tail)

                content = list(content)

                for test in [mt[0] for mt in match_templates]:
                    test(tail[0][0:3], namespaces, ctxt, updateonly=True)

                def select(path):
                    return adapters.InlinePath(path).select(Stream(content), namespaces, ctxt)
                
                for event in _match(template(select), ctxt, match_templates[:idx] + match_templates[idx + 1:]):
                    yield event
                break
        else:
            yield event

def evaluate(result, pos):
    if result is not None:
        if isinstance(result, basestring):
            yield TEXT, result, pos, result
        elif hasattr(result, '__iter__'):
            for event in result:
                yield event
        else:
            yield TEXT, unicode(result), pos, result

