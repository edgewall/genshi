#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2010 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError, DistutilsPlatformError
import os
try:
    from setuptools import setup, Extension
    from setuptools.command.bdist_egg import bdist_egg
except ImportError:
    from distutils.core import setup, Extension
    bdist_egg = None
import sys

sys.path.append(os.path.join('doc', 'common'))
try:
    from doctools import build_doc, test_doc
except ImportError:
    build_doc = test_doc = None

_speedup_available = False

is_pypy = hasattr(sys, 'pypy_version_info')

class optional_build_ext(build_ext):
    # This class allows C extension building to fail.
    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            _etype, e, _tb = sys.exc_info()
            self._unavailable(e)

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
            global _speedup_available
            _speedup_available = True
        except CCompilerError:
            _etype, e, _tb = sys.exc_info()
            self._unavailable(e)

    def _unavailable(self, exc):
        print('*' * 70)
        print("""WARNING:
An optional C extension could not be compiled, speedups will not be
available.""")
        print('*' * 70)
        print(exc)


# Optional C extension module for speeding up Genshi
# Not activated by default on:
# - PyPy (where it harms performance)
_speedup_enable_default = 0 if is_pypy else 1
try:
    _speedup_enabled = int(os.getenv('GENSHI_BUILD_SPEEDUP', _speedup_enable_default))
except ValueError:
    import warnings
    warnings.warn('GENSHI_BUILD_SPEEDUP was defined to something other than 0 or 1; defaulting to not build...')
    _speedup_enabled = False

ext_modules = []
if _speedup_enabled:
    ext_modules.append(Extension('genshi._speedups', ['genshi/_speedups.c']))


# Setuptools need some help figuring out if the egg is "zip_safe" or not
if bdist_egg:
    class my_bdist_egg(bdist_egg):
        def zip_safe(self):
            return not _speedup_available and bdist_egg.zip_safe(self)


cmdclass = {'build_doc': build_doc, 'test_doc': test_doc,
            'build_ext': optional_build_ext}
if bdist_egg:
    cmdclass['bdist_egg'] = my_bdist_egg


extra = {}
if sys.version_info >= (3,):
    # Install genshi template tests
    extra['include_package_data'] = True


setup(
    test_suite = 'genshi.tests.suite',
    ext_modules = ext_modules,
    cmdclass = cmdclass,
    **extra
)
