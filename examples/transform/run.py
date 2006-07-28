#!/usr/bin/python
# -*- coding: utf-8 -*-

import os

from markup.input import HTMLParser
from markup.template import Context, TemplateLoader

def run():
    basepath = os.path.dirname(os.path.abspath(__file__))
    loader = TemplateLoader([basepath])
    html_filename = os.path.join(basepath, 'index.html')
    html_fileobj = open(html_filename)
    try:
        html = HTMLParser(html_fileobj, html_filename)
        tmpl = loader.load('template.xml')
        print tmpl.generate(Context(input=html)).render('xhtml')
    finally:
        html_fileobj.close()


if __name__ == '__main__':
    run()
