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

import os
from setuptools import setup, Extension
from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError, DistutilsPlatformError
import sys

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

cmdclass = {'build_ext': optional_build_ext}

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
