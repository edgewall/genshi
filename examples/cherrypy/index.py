import os
import sys

import cherrypy
from genshi.template import TemplateLoader

loader = TemplateLoader([os.path.dirname(os.path.abspath(__file__))])


class Example(object):

    @cherrypy.expose
    def index(self):
        tmpl = loader.load('index.html')
        return tmpl.generate(name='world').render('xhtml')


cherrypy.root = Example()

if __name__ == '__main__':
    cherrypy.config.update(file='config.txt')
    cherrypy.server.start()
