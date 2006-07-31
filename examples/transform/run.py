#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys

from markup.input import HTMLParser
from markup.template import Context, Template

def transform(html_filename, tmpl_filename):
    tmpl_fileobj = open(tmpl_filename)
    tmpl = Template(tmpl_fileobj, tmpl_filename)
    tmpl_fileobj.close()

    html_fileobj = open(html_filename)
    html = HTMLParser(html_fileobj, html_filename)
    print tmpl.generate(Context(input=html)).render('xhtml')
    html_fileobj.close()

if __name__ == '__main__':
    basepath = os.path.dirname(os.path.abspath(__file__))
    tmpl_filename = os.path.join(basepath, 'template.xml')
    html_filename = os.path.join(basepath, 'index.html')
    transform(html_filename, tmpl_filename)
