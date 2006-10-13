# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# Copyright (C) 2006 Matthew Good
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Basic support for the template engine plugin API used by TurboGears and
CherryPy/Buffet.
"""

from pkg_resources import resource_filename

from genshi.eval import Undefined
from genshi.input import ET, HTML, XML
from genshi.template import Context, MarkupTemplate, Template, TemplateLoader, \
                            TextTemplate


class AbstractTemplateEnginePlugin(object):
    """Implementation of the plugin API."""

    template_class = None
    extension = None

    def __init__(self, extra_vars_func=None, options=None):
        if options is None:
            options = {}
        # TODO get loader_args from the options dict

        self.loader = TemplateLoader(auto_reload=True)
        self.options = options
        self.get_extra_vars = extra_vars_func

    def load_template(self, templatename, template_string=None):
        """Find a template specified in python 'dot' notation, or load one from
        a string.
        """
        if template_string is not None:
            return self.template_class(template_string)

        divider = templatename.rfind('.')
        if divider >= 0:
            package = templatename[:divider]
            basename = templatename[divider + 1:] + self.extension
            templatename = resource_filename(package, basename)

        return self.loader.load(templatename, cls=self.template_class)

    def render(self, info, format='html', fragment=False, template=None):
        """Render the template to a string using the provided info."""
        return self.transform(info, template).render(method=format)

    def transform(self, info, template):
        """Render the output to an event stream."""
        if not isinstance(template, Template):
            template = self.load_template(template)
        ctxt = Context(**info)

        # Some functions for Kid compatibility
        def defined(name):
            return ctxt.get(name, Undefined) is not Undefined
        ctxt['defined'] = defined
        def value_of(name, default=None):
            return ctxt.get(name, default)
        ctxt['value_of'] = value_of

        return template.generate(ctxt)


class MarkupTemplateEnginePlugin(AbstractTemplateEnginePlugin):
    """Implementation of the plugin API for markup templates."""

    template_class = MarkupTemplate
    extension = '.html'

    def transform(self, info, template):
        """Render the output to an event stream."""
        data = {'ET': ET, 'HTML': HTML, 'XML': XML}
        if self.get_extra_vars:
            data.update(self.get_extra_vars())
        data.update(info)
        return super(MarkupTemplateEnginePlugin, self).transform(data, template)


class TextTemplateEnginePlugin(AbstractTemplateEnginePlugin):
    """Implementation of the plugin API for text templates."""

    template_class = TextTemplate
    extension = '.txt'

    def transform(self, info, template):
        """Render the output to an event stream."""
        data = {}
        if self.get_extra_vars:
            data.update(self.get_extra_vars())
        data.update(info)
        return super(TextTemplateEnginePlugin, self).transform(data, template)
