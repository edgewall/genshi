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

"""Markup templating engine."""

from itertools import chain

from genshi.core import Attrs, Namespace, Stream, StreamEventKind
from genshi.core import START, END, START_NS, END_NS, TEXT, COMMENT
from genshi.input import XMLParser
from genshi.template.core import BadDirectiveError, Template, \
                                 _apply_directives, SUB
from genshi.template.loader import TemplateNotFound
from genshi.template.directives import *


class MarkupTemplate(Template):
    """Implementation of the template language for XML-based templates.
    
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:for="item in items">${item}</li>
    ... </ul>''')
    >>> print tmpl.generate(items=[1, 2, 3])
    <ul>
      <li>1</li><li>2</li><li>3</li>
    </ul>
    """
    INCLUDE = StreamEventKind('INCLUDE')

    DIRECTIVE_NAMESPACE = Namespace('http://genshi.edgewall.org/')
    XINCLUDE_NAMESPACE = Namespace('http://www.w3.org/2001/XInclude')

    directives = [('def', DefDirective),
                  ('match', MatchDirective),
                  ('when', WhenDirective),
                  ('otherwise', OtherwiseDirective),
                  ('for', ForDirective),
                  ('if', IfDirective),
                  ('choose', ChooseDirective),
                  ('with', WithDirective),
                  ('replace', ReplaceDirective),
                  ('content', ContentDirective),
                  ('attrs', AttrsDirective),
                  ('strip', StripDirective)]

    def __init__(self, source, basedir=None, filename=None, loader=None,
                 encoding=None):
        """Initialize a template from either a string or a file-like object."""
        Template.__init__(self, source, basedir=basedir, filename=filename,
                          loader=loader, encoding=encoding)

        self.filters.append(self._match)
        if loader:
            self.filters.append(self._include)

    def _parse(self, source, encoding):
        """Parse the template from an XML document."""
        streams = [[]] # stacked lists of events of the "compiled" template
        dirmap = {} # temporary mapping of directives to elements
        ns_prefix = {}
        depth = 0
        in_fallback = 0
        include_href = None

        if not isinstance(source, Stream):
            source = XMLParser(source, filename=self.filename,
                               encoding=encoding)

        for kind, data, pos in source:
            stream = streams[-1]

            if kind is START_NS:
                # Strip out the namespace declaration for template directives
                prefix, uri = data
                ns_prefix[prefix] = uri
                if uri not in (self.DIRECTIVE_NAMESPACE,
                               self.XINCLUDE_NAMESPACE):
                    stream.append((kind, data, pos))

            elif kind is END_NS:
                uri = ns_prefix.pop(data, None)
                if uri and uri not in (self.DIRECTIVE_NAMESPACE,
                                       self.XINCLUDE_NAMESPACE):
                    stream.append((kind, data, pos))

            elif kind is START:
                # Record any directive attributes in start tags
                tag, attrs = data
                directives = []
                strip = False

                if tag in self.DIRECTIVE_NAMESPACE:
                    cls = self._dir_by_name.get(tag.localname)
                    if cls is None:
                        raise BadDirectiveError(tag.localname, self.filepath,
                                                pos[1])
                    value = attrs.get(getattr(cls, 'ATTRIBUTE', None), '')
                    directives.append((cls, value, ns_prefix.copy(), pos))
                    strip = True

                new_attrs = []
                for name, value in attrs:
                    if name in self.DIRECTIVE_NAMESPACE:
                        cls = self._dir_by_name.get(name.localname)
                        if cls is None:
                            raise BadDirectiveError(name.localname,
                                                    self.filepath, pos[1])
                        directives.append((cls, value, ns_prefix.copy(), pos))
                    else:
                        if value:
                            value = list(self._interpolate(value, self.basedir,
                                                           *pos))
                            if len(value) == 1 and value[0][0] is TEXT:
                                value = value[0][1]
                        else:
                            value = [(TEXT, u'', pos)]
                        new_attrs.append((name, value))
                new_attrs = Attrs(new_attrs)

                if directives:
                    index = self._dir_order.index
                    directives.sort(lambda a, b: cmp(index(a[0]), index(b[0])))
                    dirmap[(depth, tag)] = (directives, len(stream), strip)

                if tag in self.XINCLUDE_NAMESPACE:
                    if tag.localname == 'include':
                        include_href = new_attrs.get('href')
                        if not include_href:
                            raise TemplateSyntaxError('Include misses required '
                                                      'attribute "href"', *pos)
                        streams.append([])
                    elif tag.localname == 'fallback':
                        in_fallback += 1

                else:
                    stream.append((kind, (tag, new_attrs), pos))

                depth += 1

            elif kind is END:
                depth -= 1

                if in_fallback and data == self.XINCLUDE_NAMESPACE['fallback']:
                    in_fallback -= 1
                elif data == self.XINCLUDE_NAMESPACE['include']:
                    fallback = streams.pop()
                    stream = streams[-1]
                    stream.append((INCLUDE, (include_href, fallback), pos))
                else:
                    stream.append((kind, data, pos))

                # If there have have directive attributes with the corresponding
                # start tag, move the events inbetween into a "subprogram"
                if (depth, data) in dirmap:
                    directives, start_offset, strip = dirmap.pop((depth, data))
                    substream = stream[start_offset:]
                    if strip:
                        substream = substream[1:-1]
                    stream[start_offset:] = [(SUB, (directives, substream),
                                              pos)]

            elif kind is TEXT:
                for kind, data, pos in self._interpolate(data, self.basedir,
                                                         *pos):
                    stream.append((kind, data, pos))

            elif kind is COMMENT:
                if not data.lstrip().startswith('!'):
                    stream.append((kind, data, pos))

            else:
                stream.append((kind, data, pos))

        assert len(streams) == 1
        return streams[0]

    def _prepare(self, stream):
        for kind, data, pos in Template._prepare(self, stream):
            if kind is INCLUDE:
                data = data[0], list(self._prepare(data[1]))
            yield kind, data, pos

    def _include(self, stream, ctxt):
        """Internal stream filter that performs inclusion of external
        template files.
        """
        for event in stream:
            if event[0] is INCLUDE:
                href, fallback = event[1]
                if not isinstance(href, basestring):
                    parts = []
                    for subkind, subdata, subpos in self._eval(href, ctxt):
                        if subkind is TEXT:
                            parts.append(subdata)
                    href = u''.join([x for x in parts if x is not None])
                try:
                    tmpl = self.loader.load(href, relative_to=event[2][0])
                    for event in tmpl.generate(ctxt):
                        yield event
                except TemplateNotFound:
                    if fallback is None:
                        raise
                    for filter_ in self.filters:
                        fallback = filter_(iter(fallback), ctxt)
                    for event in fallback:
                        yield event
            else:
                yield event

    def _match(self, stream, ctxt, match_templates=None):
        """Internal stream filter that applies any defined match templates
        to the stream.
        """
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

            # We (currently) only care about start and end events for matching
            # We might care about namespace events in the future, though
            if not match_templates or (event[0] is not START and
                                       event[0] is not END):
                yield event
                continue

            for idx, (test, path, template, namespaces, directives) in \
                    enumerate(match_templates):

                if test(event, namespaces, ctxt) is True:

                    # Let the remaining match templates know about the event so
                    # they get a chance to update their internal state
                    for test in [mt[0] for mt in match_templates[idx + 1:]]:
                        test(event, namespaces, ctxt, updateonly=True)

                    # Consume and store all events until an end event
                    # corresponding to this start event is encountered
                    content = chain([event],
                                    self._match(_strip(stream), ctxt,
                                                [match_templates[idx]]),
                                    tail)
                    content = list(self._include(content, ctxt))

                    for test in [mt[0] for mt in match_templates]:
                        test(tail[0], namespaces, ctxt, updateonly=True)

                    # Make the select() function available in the body of the
                    # match template
                    def select(path):
                        return Stream(content).select(path, namespaces, ctxt)
                    ctxt.push(dict(select=select))

                    # Recursively process the output
                    template = _apply_directives(template, ctxt, directives)
                    for event in self._match(self._eval(self._flatten(template,
                                                                      ctxt),
                                                        ctxt), ctxt,
                                             match_templates[:idx] +
                                             match_templates[idx + 1:]):
                        yield event

                    ctxt.pop()
                    break

            else: # no matches
                yield event


INCLUDE = MarkupTemplate.INCLUDE
