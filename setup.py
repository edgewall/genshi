#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.

from setuptools import setup, find_packages

setup(
    name='Markup', version='0.1',
    description='Toolkit for stream-based generation of markup for the web',
    author='Christopher Lenz', author_email='cmlenz@gmx.net',
    license='BSD', url='http://markup.cmlenz.net/',
    packages=find_packages(exclude=['*.tests*']),
    test_suite = 'markup.tests.suite',
    zip_safe = True
)
