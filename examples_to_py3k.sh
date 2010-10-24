#!/bin/sh
#
# Script to run 2to3 on files not covered by setup.py
#
export PYTHONIOENCODING=utf8

# General 2to3 run
2to3 -w --no-diffs examples/
