#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://markup.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://markup.edgewall.org/log/.

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

setup(
    name='Markup', version='0.1',
    description='Toolkit for stream-based generation of markup for the web',
    author='Edgewall Software', author_email='info@edgewall.org',
    license='BSD', url='http://markup.edgewall.org/',
    download_url='http://markup.edgewall.org/wiki/MarkupDownload',
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

    packages=['markup'],

    test_suite = 'markup.tests.suite',
    zip_safe = True,
    entry_points = """
    [python.templating.engines]
    markup = markup.plugin:TemplateEnginePlugin
    """,
)
