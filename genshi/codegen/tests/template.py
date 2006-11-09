from genshi.tests import template
from genshi.template import MarkupTemplate as RealMarkupTemplate
from genshi.codegen.generator import Generator
from genshi.codegen.serialize import HTMLSerializeFilter


import unittest

# original template unittest does this:
# tmpl = MarkupTemplate(text)
# result = str(tmpl.generate(items=items)))

class MarkupTemplateAdapter(object):
    def __init__(self, text):
        self.generator = Generator(RealMarkupTemplate(text), strip_whitespace=True, compress_empty=True)
        print u''.join(self.generator._generate_code_events())
    def generate(self, *args, **kwargs):
        return self.generator.generate(*args, **kwargs)

        
template.MarkupTemplate = MarkupTemplateAdapter

from genshi.tests.template import *



def suite():
    return template.suite()

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
