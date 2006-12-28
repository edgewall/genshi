#!/usr/bin/env python
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

from distutils.cmd import Command
import doctest
from glob import glob
import os
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


class build_doc(Command):
    description = 'Builds the documentation'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from docutils.core import publish_cmdline
        conf = os.path.join('doc', 'docutils.conf')

        for source in glob('doc/*.txt'):
            dest = os.path.splitext(source)[0] + '.html'
            if not os.path.exists(dest) or \
                   os.path.getmtime(dest) < os.path.getmtime(source):
                print 'building documentation file %s' % dest
                publish_cmdline(writer_name='html',
                                argv=['--config=%s' % conf, source, dest])


class test_doc(Command):
    description = 'Tests the code examples in the documentation'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        for filename in glob('doc/*.txt'):
            print 'testing documentation file %s' % filename
            doctest.testfile(filename, False, optionflags=doctest.ELLIPSIS)


setup(
    name = 'Genshi',
    version = '0.4',
    description = 'A toolkit for stream-based generation of output for the web',
    long_description = \
"""Genshi is a Python library that provides an integrated set of components
for parsing, generating, and processing HTML, XML or other textual content for
output generation on the web. The major feature is a template language, which
is heavily inspired by Kid.""",
    author = 'Edgewall Software',
    author_email = 'info@edgewall.org',
    license = 'BSD',
    url = 'http://genshi.edgewall.org/',
    download_url = 'http://genshi.edgewall.org/wiki/Download',
    zip_safe = True,

    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Markup :: HTML',
        'Topic :: Text Processing :: Markup :: XML'
    ],
    keywords = ['python.templating.engines'],
    packages = ['genshi', 'genshi.template'],
    test_suite = 'genshi.tests.suite',

    extras_require = {'plugin': ['setuptools>=0.6a2']},
    entry_points = """
    [python.templating.engines]
    genshi = genshi.template.plugin:MarkupTemplateEnginePlugin[plugin]
    genshi-markup = genshi.template.plugin:MarkupTemplateEnginePlugin[plugin]
    genshi-text = genshi.template.plugin:TextTemplateEnginePlugin[plugin]
    """,

    cmdclass={'build_doc': build_doc, 'test_doc': test_doc}
)
