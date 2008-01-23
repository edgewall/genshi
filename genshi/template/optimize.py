# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.


from genshi.core import Stream, Markup, StreamEventKind, START, END, TEXT, \
                        XML_DECL, DOCTYPE, START_NS, END_NS, START_CDATA, \
                        END_CDATA, PI, COMMENT, OPTIMIZER, _ensure
from genshi.output import XMLSerializer, EmptyTagFilter, WhitespaceFilter, \
                          NamespaceFlattener, DocTypeInserter, encode, \
                          get_serializer
from genshi.template.base import Context, EXPR, SUB
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset


__all__ = ['Optimizer', 'StaticStrategy', 'InvariantStrategy']


"""
Optimisation occurs in three phases:

Template Analysis
-----------------
Analysis of the pre-parsed stream stored in the Template. Strategies will
typically insert OPTIMIZER marks around sequences of events they are interested
in.

Serialisation
-------------
Normally during serialisation the rendered fragments are sent directly to the
output destination. OPTIMIZER fragments are passed untouched through this stage
and would normally be sent to output, but the Optimizer intercepts the stream
and passes it to the Strategies for further analysis, before finally sending it
to the output destination.

Details
-------

There are two main methods of increasing performance in Genshi: reducing the
number of events that need rendering, and decreasing the total number of events
that require processing at all.

An example of both is implemented by the StaticStrategy. This strategy operates
by analysing the template render in the first pass, then modifying the template
stream in-place.

The optimisation occurs in these steps:

  - Analysis starts by inserting STATIC_START and STATIC_END events around
    sequences of normal events that are not dynamic in any way.
  - The rendered stream is then inspected at the end of the pipeline and
    sequences of rendered Markup objects between these two events merged
    into one event.
  - The strategy then replaces the corresponding span in the original template
    stream with a single STATIC event with the conjoined Markup as the
    data payload.
  - Finally, the strategy sets a flag that disables analysis and expands
    STATIC events during serialisation.

Note that all OPTIMIZER events must be in the form:

    (OPTIMIZER, (optimizer_kind, data), pos)

eg. The input stream:

  ('START', (QName(u'div'), Attrs()), (None, 1, 0))
  ('TEXT', u'Some ', (None, 1, 5))
  ('START', (QName(u'em'), Attrs()), (None, 1, 10))
  ('TEXT', u'EMPHASISED', (None, 1, 14))
  ('END', QName(u'em'), (None, 1, 24))
  ('TEXT', u' text.', (None, 1, 29))
  ('END', QName(u'div'), (None, 1, 35))

Would look like this during template analysis:

  ('OPTIMIZER', ('STATIC_START', None), None)
  ('START', (QName(u'div'), Attrs()), (None, 1, 0))
  ...
  ('END', QName(u'div'), (None, 1, 35))
  ('OPTIMIZER', ('STATIC_END', None), None)

Then this during serialisation:

  ('OPTIMIZER', ('STATIC_START', None), None)
  <Markup u'<div>'>
  <Markup u'Some '>
  <Markup u'<em>'>
  <Markup u'EMPHASISED'>
  <Markup u'</em>'>
  <Markup u' text.'>
   <Markup u'</div>'>
  ('OPTIMIZER', ('STATIC_END', None), None)

The template stream would then be optimised to this:

  ('OPTIMIZER', ('STATIC', Markup('<div>Some <em>EMPHASISED</em> text.</div>')), None)

Further renders would result in this single event traversing the pipeline and
finally being rendered by the strategy after normal serialisation.

Note: This is kept as an OPTIMIZER event rather than replacing it with TEXT
because the latter undergoes a fair amount of processing on every traversal,
steps that are unnecessary for an already rendered fragment.
"""

class OptimizingStream(Stream):
    def __init__(self, optimizer, ctxt, *args, **kwargs):
        super(OptimizingStream, self).__init__(*args, **kwargs)
        self.optimizer = optimizer
        self.ctxt = ctxt
        self.apply = True

    def serialize(self, method='xml', *args, **kwargs):
        if method is None:
            method = self.serializer or 'xml'
        stream = list(get_serializer(*args, **kwargs)(_ensure(self)))
        if self.apply:
            stream = self.optimizer.apply_serialization(stream, self.ctxt)
        for event in stream:
            yield event
        if self.apply:
            self.optimizer.apply_optimizations(self.ctxt)

    def __or__(self, function):
        self.apply = False
        return OptimizingStream(self.optimizer, self.ctxt,
                                _ensure(function(self)))


class Strategy(object):
    """A stub optimization strategy.

    Note: Unimplemented phases will not impact performance.
    """
    def bind(self, optimizer, template):
        """Bind this strategy to a Template.
        
        This is called once.
        """
        self.optimizer = optimizer
        self.template = template

    def analyze(self, stream, ctxt):
        """Analyze the Template stream.

        This occurs prior to every run of Template.generate().

        Typically involves injecting analysis markers into the stream.
        """
        return stream

    def serialize(self, stream, ctxt):
        """Post-serialization hook.
        
        This is typically where optimizations are applied to the render stage,
        and also where rendered fragments are collected for use in """
        return stream

    def optimize(self, stream, ctxt):
        """Apply optimizations to the Template stream.

        This occurs after serialization on every run.
        """
        return stream


class StaticStrategy(Strategy):
    STATIC = StreamEventKind('STATIC')
    STATIC_START = StreamEventKind('STATIC_START')
    STATIC_END = StreamEventKind('STATIC_END')

    STATIC_KINDS = frozenset([TEXT, XML_DECL, DOCTYPE, START_NS, END_NS,
                              START_CDATA, END_CDATA, PI, COMMENT])

    def __init__(self):
        self.fragment_map = {}
        self.optimized = False
        self.analyzed = False

    def analyze(self, stream, ctxt, depth=0):
        if self.analyzed:
            for event in stream:
                yield event
            return

        inside = False
        static_start = []
        index = 0
        for kind, data, pos in stream:
            static = True
            key = depth, index
            if kind is START:
                tag, attrs = data
                for name, substream in attrs:
                    if not isinstance(substream, basestring):
                        static = False
                        break
                static_start.append(static)
            elif kind is END:
                static = static_start.pop()
            elif kind in STATIC_KINDS:
                static = True
            elif kind is SUB:
                directives, substream = data
                substream = list(self.analyze(substream, ctxt, depth + 1))
                data = directives, substream
                static = False
            else:
                static = False

            if inside and not static:
                yield OPTIMIZER, (STATIC_END, None), None
                index += 1
                inside = False
            elif not inside and static:
                yield OPTIMIZER, (STATIC_START, key), None
                inside = True
            yield (kind, data, pos)

        if inside:
            yield OPTIMIZER, (STATIC_END, None), None

        if not depth:
            self.analyzed = True

    def serialize(self, stream, ctxt, depth=0):
        inside = None
        buffer = []
        for event in stream:
            kind = event[0]
            if kind is OPTIMIZER:
                okind, data = event[1]
                if okind is STATIC:
                    yield data
                    continue
                elif okind is STATIC_START:
                    inside = event
                    continue
                elif okind is STATIC_END:
                    # Only compact spans of more than one event
                    if len(buffer) > 1:
                        key = inside[1][1]
                        fragment = Markup().join(buffer)
                        self.fragment_map[key] = fragment
                        yield fragment
                        buffer = []
                        inside = None
                        continue

                    inside = None
                    buffer = []
                    continue

            if inside:
                buffer.append(event)
                continue

            yield event

        if inside and buffer:
            key = inside[1][1]
            fragment = Markup().join(buffer)
            self.fragment_map[key] = fragment
            yield fragment

    def optimize(self, stream, ctxt, depth=0):
        if self.optimized:
            for event in stream:
                yield event
            return

        inside = False
        index = 0
        for kind, data, pos in stream:
            if inside:
                if kind is OPTIMIZER:
                    inside = False
                continue

            if kind is OPTIMIZER:
                if data[0] is STATIC_START:
                    if data[1] in self.fragment_map:
                        yield (OPTIMIZER,
                               (STATIC, self.fragment_map[data[1]]),
                               None)
                    inside = True
                    continue

            elif kind is SUB:
                directives, substream = data
                substream = list(self.optimize(substream, ctxt, depth + 1))
                data = directives, substream

            yield kind, data, pos


STATIC = StaticStrategy.STATIC
STATIC_START = StaticStrategy.STATIC_START
STATIC_END = StaticStrategy.STATIC_END
STATIC_KINDS = StaticStrategy.STATIC_KINDS


class Optimizer(object):
    """Apply optimization strategies during Template rendering."""

    serializer = 'xml'

    def __init__(self, template, strategies=None):
        self.template = template
        self.strategies = strategies or []
        self.configure()

    def configure(self):
        """Configure strategies on template."""
        for strategy in self.strategies:
            strategy.bind(self, self.template)

    def generate(self, *args, **kwargs):
        if args:
            assert len(args) == 1
            ctxt = args[0]
            if ctxt is None:
                ctxt = Context(**kwargs)
            assert isinstance(ctxt, Context)
        else:
            ctxt = Context(**kwargs)

        self.apply_analysis(ctxt)

        stream = self.template.stream
        for filter_ in self.template.filters:
            stream = filter_(iter(stream), ctxt)

        return OptimizingStream(self, ctxt, stream)

    def apply_strategy_stage(self, ctxt, stage):
        stream = self.template.stream
        for strategy in self.strategies:
            stream = getattr(strategy, stage)(stream, ctxt)
        if not isinstance(stream, list):
            stream = list(stream)
        self.template.stream = stream

    def apply_analysis(self, ctxt):
        self.apply_strategy_stage(ctxt, 'analyze')

    def apply_optimizations(self, ctxt):
        self.apply_strategy_stage(ctxt, 'optimize')

    def apply_serialization(self, stream, ctxt):
        for strategy in self.strategies:
            stream = strategy.serialize(stream, ctxt)
        return stream

