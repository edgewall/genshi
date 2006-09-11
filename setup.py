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

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name = 'Genshi',
    version = '0.3',
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
    download_url = 'http://genshi.edgewall.org/wiki/GenshiDownload',
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
    packages = ['genshi'],
    test_suite = 'genshi.tests.suite',

    extras_require = {'plugin': ['setuptools>=0.6a2']},
    entry_points = """
    [python.templating.engines]
    genshi = genshi.plugin:TemplateEnginePlugin[plugin]
    """,
)
