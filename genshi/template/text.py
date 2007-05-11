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

"""Plain text templating engine."""

import re

from genshi.template.base import BadDirectiveError, Template, INCLUDE, SUB
from genshi.template.directives import *
from genshi.template.directives import Directive, _apply_directives
from genshi.template.interpolation import interpolate

__all__ = ['TextTemplate']
__docformat__ = 'restructuredtext en'


class TextTemplate(Template):
    """Implementation of a simple text-based template engine.
    
    >>> tmpl = TextTemplate('''Dear $name,
    ... 
    ... We have the following items for you:
    ... #for item in items
    ...  * $item
    ... #end
    ... 
    ... All the best,
    ... Foobar''')
    >>> print tmpl.generate(name='Joe', items=[1, 2, 3]).render('text')
    Dear Joe,
    <BLANKLINE>
    We have the following items for you:
     * 1
     * 2
     * 3
    <BLANKLINE>
    All the best,
    Foobar
    """
    directives = [('def', DefDirective),
                  ('when', WhenDirective),
                  ('otherwise', OtherwiseDirective),
                  ('for', ForDirective),
                  ('if', IfDirective),
                  ('choose', ChooseDirective),
                  ('with', WithDirective)]

    _DIRECTIVE_RE = re.compile(r'(?:^[ \t]*(?<!\\)#(end).*\n?)|'
                               r'(?:^[ \t]*(?<!\\)#((?:\w+|#).*)\n?)',
                               re.MULTILINE)

    def _parse(self, source, encoding):
        """Parse the template from text input."""
        stream = [] # list of events of the "compiled" template
        dirmap = {} # temporary mapping of directives to elements
        depth = 0
        if not encoding:
            encoding = 'utf-8'

        source = source.read().decode(encoding, 'replace')
        offset = 0
        lineno = 1

        for idx, mo in enumerate(self._DIRECTIVE_RE.finditer(source)):
            start, end = mo.span()
            if start > offset:
                text = source[offset:start]
                for kind, data, pos in interpolate(text, self.basedir,
                                                   self.filename, lineno,
                                                   lookup=self.lookup):
                    stream.append((kind, data, pos))
                lineno += len(text.splitlines())

            text = source[start:end].lstrip()[1:]
            lineno += len(text.splitlines())
            directive = text.split(None, 1)
            if len(directive) > 1:
                command, value = directive
            else:
                command, value = directive[0], None

            if command == 'end':
                depth -= 1
                if depth in dirmap:
                    directive, start_offset = dirmap.pop(depth)
                    substream = stream[start_offset:]
                    stream[start_offset:] = [(SUB, ([directive], substream),
                                              (self.filepath, lineno, 0))]
            elif command == 'include':
                pos = (self.filename, lineno, 0)
                stream.append((INCLUDE, (value.strip(), []), pos))
            elif command != '#':
                cls = self._dir_by_name.get(command)
                if cls is None:
                    raise BadDirectiveError(command)
                directive = cls, value, None, (self.filepath, lineno, 0)
                dirmap[depth] = (directive, len(stream))
                depth += 1

            offset = end

        if offset < len(source):
            text = source[offset:].replace('\\#', '#')
            for kind, data, pos in interpolate(text, self.basedir,
                                               self.filename, lineno,
                                               lookup=self.lookup):
                stream.append((kind, data, pos))

        return stream
