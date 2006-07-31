from cgi import escape
import os
from StringIO import StringIO
import sys
import timeit

__all__ = ['clearsilver', 'django', 'kid', 'markup', 'simpletal']

def markup(dirname, verbose=False):
    from markup.template import Context, TemplateLoader
    loader = TemplateLoader([dirname], auto_reload=False)
    template = loader.load('template.html')
    def render():
        ctxt = Context(title='Just a test', user='joe',
                       items=['Number %d' % num for num in range(1, 15)])
        return template.generate(ctxt).render('html')

    if verbose:
        print render()
    return render

def cheetah(dirname, verbose=False):
    # FIXME: infinite recursion somewhere... WTF?
    from Cheetah.Template import Template
    class MyTemplate(Template):
        def serverSidePath(self, path): return os.path.join(dirname, path)
    filename = os.path.join(dirname, 'template.tmpl')
    template = MyTemplate(file=filename)

    def render():
        template = MyTemplate(file=filename,
                              searchList=[{'title': 'Just a test', 'user': 'joe',
                                           'items': [u'Number %d' % num for num in range(1, 15)]}])
        return template.respond()

    if verbose:
        print render()
    return render

def clearsilver(dirname, verbose=False):
    import neo_cgi
    neo_cgi.update()
    import neo_util
    import neo_cs
    def render():
        hdf = neo_util.HDF()
        hdf.setValue('hdf.loadpaths.0', dirname)
        hdf.setValue('title', escape('Just a test'))
        hdf.setValue('user', escape('joe'))
        for num in range(1, 15):
            hdf.setValue('items.%d' % (num - 1), escape('Number %d' % num))
        cs = neo_cs.CS(hdf)
        cs.parseFile('template.cs')
        return cs.render()

    if verbose:
        print render()
    return render

def django(dirname, verbose=False):
    from django.conf import settings
    settings.configure(TEMPLATE_DIRS=[os.path.join(dirname, 'templates')])
    from django import template, templatetags
    from django.template import loader
    templatetags.__path__.append(os.path.join(dirname, 'templatetags'))
    tmpl = loader.get_template('template.html')

    def render():
        data = {'title': 'Just a test', 'user': 'joe',
                'items': ['Number %d' % num for num in range(1, 15)]}
        return tmpl.render(template.Context(data))

    if verbose:
        print render()
    return render

def kid(dirname, verbose=False):
    import kid
    kid.path = kid.TemplatePath([dirname])
    template = kid.Template(file='template.kid')
    def render():
        template = kid.Template(file='template.kid',
                                title='Just a test', user='joe',
                                items=['Number %d' % num for num in range(1, 15)])
        return template.serialize(output='xhtml')

    if verbose:
        print render()
    return render

def nevow(dirname, verbose=False):
    # FIXME: can't figure out the API
    from nevow.loaders import xmlfile
    template = xmlfile('template.xml', templateDir=dirname).load()
    def render():
        print template

    if verbose:
        print render()
    return render

def simpletal(dirname, verbose=False):
    from simpletal import simpleTAL, simpleTALES
    fileobj = open(os.path.join(dirname, 'base.html'))
    base = simpleTAL.compileHTMLTemplate(fileobj)
    fileobj.close()
    fileobj = open(os.path.join(dirname, 'template.html'))
    template = simpleTAL.compileHTMLTemplate(fileobj)
    fileobj.close()
    def render():
        ctxt = simpleTALES.Context(allowPythonPath=1)
        ctxt.addGlobal('base', base)
        ctxt.addGlobal('title', 'Just a test')
        ctxt.addGlobal('user', 'joe')
        ctxt.addGlobal('items', ['Number %d' % num for num in range(1, 15)])
        buf = StringIO()
        template.expand(ctxt, buf)
        return buf.getvalue()

    if verbose:
        print render()
    return render

def run(engines, verbose=False):
    basepath = os.path.abspath(os.path.dirname(__file__))
    for engine in engines:
        dirname = os.path.join(basepath, engine)
        if verbose:
            print '%s:' % engine.capitalize()
            print '--------------------------------------------------------'
        else:
            print '%s:' % engine.capitalize(),
        t = timeit.Timer(setup='from __main__ import %s; render = %s("%s", %s)'
                               % (engine, engine, dirname, verbose),
                         stmt='render()')
        time = t.timeit(number=2000) / 2000
        if verbose:
            print '--------------------------------------------------------'
        print '%.2f ms' % (1000 * time)
        if verbose:
            print '--------------------------------------------------------'


if __name__ == '__main__':
    engines = [arg for arg in sys.argv[1:] if arg[0] != '-']
    if not engines:
        engines = __all__

    verbose = '-v' in sys.argv

    if '-p' in sys.argv:
        import hotshot, hotshot.stats
        prof = hotshot.Profile("template.prof")
        benchtime = prof.runcall(run, engines, verbose=verbose)
        stats = hotshot.stats.load("template.prof")
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats()
    else:
        run(engines, verbose=verbose)
