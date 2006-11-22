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

"""Template loading and caching."""

import os
try:
    import threading
except ImportError:
    import dummy_threading as threading

from genshi.template.core import TemplateError
from genshi.util import LRUCache

__all__ = ['TemplateLoader', 'TemplateNotFound']


class TemplateNotFound(TemplateError):
    """Exception raised when a specific template file could not be found."""

    def __init__(self, name, search_path):
        TemplateError.__init__(self, 'Template "%s" not found' % name)
        self.search_path = search_path


class TemplateLoader(object):
    """Responsible for loading templates from files on the specified search
    path.
    
    >>> import tempfile
    >>> fd, path = tempfile.mkstemp(suffix='.html', prefix='template')
    >>> os.write(fd, '<p>$var</p>')
    11
    >>> os.close(fd)
    
    The template loader accepts a list of directory paths that are then used
    when searching for template files, in the given order:
    
    >>> loader = TemplateLoader([os.path.dirname(path)])
    
    The `load()` method first checks the template cache whether the requested
    template has already been loaded. If not, it attempts to locate the
    template file, and returns the corresponding `Template` object:
    
    >>> from genshi.template import MarkupTemplate
    >>> template = loader.load(os.path.basename(path))
    >>> isinstance(template, MarkupTemplate)
    True
    
    Template instances are cached: requesting a template with the same name
    results in the same instance being returned:
    
    >>> loader.load(os.path.basename(path)) is template
    True
    
    >>> os.remove(path)
    """
    def __init__(self, search_path=None, auto_reload=False,
                 default_encoding=None, max_cache_size=25, default_class=None):
        """Create the template laoder.
        
        @param search_path: a list of absolute path names that should be
            searched for template files, or a string containing a single
            absolute path
        @param auto_reload: whether to check the last modification time of
            template files, and reload them if they have changed
        @param default_encoding: the default encoding to assume when loading
            templates; defaults to UTF-8
        @param max_cache_size: the maximum number of templates to keep in the
            cache
        @param default_class: the default `Template` subclass to use when
            instantiating templates
        """
        from genshi.template.markup import MarkupTemplate

        self.search_path = search_path
        if self.search_path is None:
            self.search_path = []
        elif isinstance(self.search_path, basestring):
            self.search_path = [self.search_path]
        self.auto_reload = auto_reload
        self.default_encoding = default_encoding
        self.default_class = default_class or MarkupTemplate
        self._cache = LRUCache(max_cache_size)
        self._mtime = {}
        self._lock = threading.Lock()

    def load(self, filename, relative_to=None, cls=None, encoding=None):
        """Load the template with the given name.
        
        If the `filename` parameter is relative, this method searches the search
        path trying to locate a template matching the given name. If the file
        name is an absolute path, the search path is not bypassed.
        
        If requested template is not found, a `TemplateNotFound` exception is
        raised. Otherwise, a `Template` object is returned that represents the
        parsed template.
        
        Template instances are cached to avoid having to parse the same
        template file more than once. Thus, subsequent calls of this method
        with the same template file name will return the same `Template`
        object (unless the `auto_reload` option is enabled and the file was
        changed since the last parse.)
        
        If the `relative_to` parameter is provided, the `filename` is
        interpreted as being relative to that path.
        
        @param filename: the relative path of the template file to load
        @param relative_to: the filename of the template from which the new
            template is being loaded, or `None` if the template is being loaded
            directly
        @param cls: the class of the template object to instantiate
        @param encoding: the encoding of the template to load; defaults to the
            `default_encoding` of the loader instance
        """
        if cls is None:
            cls = self.default_class
        if encoding is None:
            encoding = self.default_encoding
        if relative_to and not os.path.isabs(relative_to):
            filename = os.path.join(os.path.dirname(relative_to), filename)
        filename = os.path.normpath(filename)

        self._lock.acquire()
        try:
            # First check the cache to avoid reparsing the same file
            try:
                tmpl = self._cache[filename]
                if not self.auto_reload or \
                        os.path.getmtime(tmpl.filepath) == self._mtime[filename]:
                    return tmpl
            except KeyError:
                pass

            search_path = self.search_path
            isabs = False

            if os.path.isabs(filename):
                # Bypass the search path if the requested filename is absolute
                search_path = [os.path.dirname(filename)]
                isabs = True

            elif relative_to and os.path.isabs(relative_to):
                # Make sure that the directory containing the including
                # template is on the search path
                dirname = os.path.dirname(relative_to)
                if dirname not in search_path:
                    search_path = search_path + [dirname]
                isabs = True

            elif not search_path:
                # Uh oh, don't know where to look for the template
                raise TemplateError('Search path for templates not configured')

            for dirname in search_path:
                filepath = os.path.join(dirname, filename)
                try:
                    fileobj = open(filepath, 'U')
                    try:
                        if isabs:
                            # If the filename of either the included or the 
                            # including template is absolute, make sure the
                            # included template gets an absolute path, too,
                            # so that nested include work properly without a
                            # search path
                            filename = os.path.join(dirname, filename)
                            dirname = ''
                        tmpl = cls(fileobj, basedir=dirname, filename=filename,
                                   loader=self, encoding=encoding)
                    finally:
                        fileobj.close()
                    self._cache[filename] = tmpl
                    self._mtime[filename] = os.path.getmtime(filepath)
                    return tmpl
                except IOError:
                    continue

            raise TemplateNotFound(filename, search_path)

        finally:
            self._lock.release()
