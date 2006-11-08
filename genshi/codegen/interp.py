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
        # no need for a sub-list of directives (nor _apply_directives function) since inlined code 
        # expands all nesting explicitly (TODO: is this really true ?)
        for idx, (test, path, template, namespaces) in \
                enumerate(match_templates):

            if test(event, namespaces, ctxt) is True:
                for test in [mt[0] for mt in match_templates[idx + 1:]]:
                    test(event, namespaces, ctxt, updateonly=True)
                    
                content = chain([event], _match(_strip(stream), ctxt),
                                tail)
                # TODO: not sure if extra list of filters is needed
                #for filter_ in self.filters[3:]:
                #    content = filter_(content, ctxt)
                content = list(content)

                for test in [mt[0] for mt in match_templates]:
                    test(tail[0][0:3], namespaces, ctxt, updateonly=True)

                def select(path):
                    return adapters.InlinePath(path).select(Stream(content), namespaces, ctxt)
                
                # similarly, no need for _eval (eval is inlined) as well as _flatten (inlined code already "flattened")
                for event in _match(template(select), ctxt, match_templates[:idx] + match_templates[idx + 1:]):
                    yield event
                break
        else:
            yield event

# TODO: this adds too much overhead
def _ensure(stream):
    """Ensure that every item on the stream is actually an inline event."""
    for event in stream:
        if type(event) is not tuple:
            if hasattr(event, 'totuple'):
                event = event.totuple()
            else:
                event = TEXT, unicode(event), (None, -1, -1), unicode(event)
        yield event

def evaluate(result, pos):
    if result is not None:
        if isinstance(result, basestring):
            yield TEXT, result, pos, result
        elif hasattr(result, '__iter__'):
            substream = _ensure(result)
            for event in substream:
                yield event
        else:
            yield TEXT, unicode(result), pos, result

