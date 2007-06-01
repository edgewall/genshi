# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
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

from genshi.input import ET, HTML, XML
from genshi.output import DocType
from genshi.template.base import Template
from genshi.template.loader import TemplateLoader
from genshi.template.markup import MarkupTemplate
from genshi.template.text import TextTemplate

__all__ = ['ConfigurationError', 'AbstractTemplateEnginePlugin',
           'MarkupTemplateEnginePlugin', 'TextTemplateEnginePlugin']
__docformat__ = 'restructuredtext en'


class ConfigurationError(ValueError):
    """Exception raised when invalid plugin options are encountered."""


class AbstractTemplateEnginePlugin(object):
    """Implementation of the plugin API."""

    template_class = None
    extension = None

    def __init__(self, extra_vars_func=None, options=None):
        self.get_extra_vars = extra_vars_func
        if options is None:
            options = {}
        self.options = options

        self.default_encoding = options.get('genshi.default_encoding', 'utf-8')
        auto_reload = options.get('genshi.auto_reload', '1')
        if isinstance(auto_reload, basestring):
            auto_reload = auto_reload.lower() in ('1', 'on', 'yes', 'true')
        search_path = filter(None, options.get('genshi.search_path', '').split(':'))
        self.use_package_naming = not search_path
        try:
            max_cache_size = int(options.get('genshi.max_cache_size', 25))
        except ValueError:
            raise ConfigurationError('Invalid value for max_cache_size: "%s"' %
                                     options.get('genshi.max_cache_size'))

        lookup_errors = options.get('genshi.lookup_errors', 'lenient')
        if lookup_errors not in ('lenient', 'strict'):
            raise ConfigurationError('Unknown lookup errors mode "%s"' %
                                     lookup_errors)

        self.loader = TemplateLoader(filter(None, search_path),
                                     auto_reload=auto_reload,
                                     max_cache_size=max_cache_size,
                                     default_class=self.template_class,
                                     variable_lookup=lookup_errors)

    def load_template(self, templatename, template_string=None):
        """Find a template specified in python 'dot' notation, or load one from
        a string.
        """
        if template_string is not None:
            return self.template_class(template_string)

        if self.use_package_naming:
            divider = templatename.rfind('.')
            if divider >= 0:
                package = templatename[:divider]
                basename = templatename[divider + 1:] + self.extension
                templatename = resource_filename(package, basename)

        return self.loader.load(templatename)

    def _get_render_options(self, format=None):
        if format is None:
            format = self.default_format
        kwargs = {'method': format}
        if self.default_encoding:
            kwargs['encoding'] = self.default_encoding
        return kwargs

    def render(self, info, format=None, fragment=False, template=None):
        """Render the template to a string using the provided info."""
        kwargs = self._get_render_options(format=format)
        return self.transform(info, template).render(**kwargs)

    def transform(self, info, template):
        """Render the output to an event stream."""
        if not isinstance(template, Template):
            template = self.load_template(template)
        return template.generate(**info)


class MarkupTemplateEnginePlugin(AbstractTemplateEnginePlugin):
    """Implementation of the plugin API for markup templates."""

    template_class = MarkupTemplate
    extension = '.html'

    def __init__(self, extra_vars_func=None, options=None):
        AbstractTemplateEnginePlugin.__init__(self, extra_vars_func, options)

        default_doctype = self.options.get('genshi.default_doctype')
        if default_doctype:
            doctype = DocType.get(default_doctype)
            if doctype is None:
                raise ConfigurationError('Unknown doctype %r' % default_doctype)
            self.default_doctype = doctype
        else:
            self.default_doctype = None

        format = self.options.get('genshi.default_format', 'html').lower()
        if format not in ('html', 'xhtml', 'xml', 'text'):
            raise ConfigurationError('Unknown output format %r' % format)
        self.default_format = format

    def _get_render_options(self, format=None):
        kwargs = super(MarkupTemplateEnginePlugin,
                       self)._get_render_options(format)
        if self.default_doctype:
            kwargs['doctype'] = self.default_doctype
        return kwargs

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
    default_format = 'text'
