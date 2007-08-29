import os

import cherrypy
from genshi.core import Stream
from genshi.output import encode, get_serializer
from genshi.template import TemplateLoader

loader = TemplateLoader(
    os.path.join(os.path.dirname(__file__), '..', 'templates'),
    auto_reload=True
)

def output(filename, method=None, encoding='utf-8', **options):
    """Decorator for exposed methods to specify what template the should use
    for rendering, and which serialization method and options should be
    applied.
    """
    def decorate(func):
        def wrapper(*args, **kwargs):
            cherrypy.thread_data.template = loader.load(filename)
            serializer = get_serializer(method, **options)
            stream = func(*args, **kwargs)
            if not isinstance(stream, Stream):
                return stream
            return encode(serializer(stream), method=serializer,
                          encoding=encoding)
        return wrapper
    return decorate

def render(*args, **kwargs):
    """Function to render the given data to the template specified via the
    ``@output`` decorator.
    """
    if args:
        assert len(args) == 1, \
            'Expected exactly one argument, but got %r' % (args,)
        template = loader.load(args[0])
    else:
        template = cherrypy.thread_data.template
    return template.generate(**kwargs)
