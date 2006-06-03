# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Mattew Good
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.

import os
from pkg_resources import resource_filename

from markup.template import Context, Template, TemplateLoader


class TemplateEnginePlugin(object):

    def __init__(self, extra_vars_func=None, options=None):
        if options is None:
            options = {}
        # TODO get loader_args from the options dict

        self.loader = TemplateLoader(auto_reload=True)
        self.options = options
        self.get_extra_vars = extra_vars_func

    def load_template(self, templatename):
        """Find a template specified in python 'dot' notation."""
        divider = templatename.rfind('.')
        if divider >= 0:
            package = templatename[:divider]
            basename = templatename[divider + 1:] + '.html'
            fullpath = resource_filename(package, basename)
            dirname, templatename = os.path.split(fullpath)
            self.loader.search_path.append(dirname) # Kludge

        return self.loader.load(templatename)

    def render(self, info, format='html', fragment=False, template=None):
        """Renders the template to a string using the provided info."""
        return self.transform(info, template).render(method=format)

    def transform(self, info, template):
        "Render the output to Elements"
        if not isinstance(template, Template):
            template = self.load_template(template)

        data = {}
        if self.get_extra_vars:
            data.update(self.get_extra_vars())
        data.update(info)

        ctxt = Context(**data)
        return template.generate(ctxt)
