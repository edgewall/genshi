from cgi import escape
import os
import sys
import time
import timeit

def markup(dirname):
    from markup.template import Context, TemplateLoader
    loader = TemplateLoader([dirname], auto_reload=False)
    template = loader.load('template.html')
    def render():
        ctxt = Context(title='Just a test',
                       items=['Number %d' % num for num in range(1, 15)])
        template.generate(ctxt).render('html')
    return render

def cheetah(dirname):
    # FIXME: infinite recursion somewhere... WTF?
    try:
        from Cheetah.Template import Template
        class MyTemplate(Template):
            def serverSidePath(self, path): return os.path.join(dirname, path)
        filename = os.path.join(dirname, 'template.tmpl')
        template = MyTemplate(file=filename)

        def render():
            template = MyTemplate(file=filename,
                                  searchList=[{'title': 'Just a test',
                                               'items': [u'Number %d' % num for num in range(1, 15)]}])
            template.respond()
        return render
    except ImportError:
        return None

def clearsilver(dirname):
    try:
        import neo_cgi
        neo_cgi.update()
        import neo_util
        import neo_cs
        def render():
            hdf = neo_util.HDF()
            hdf.setValue('hdf.loadpaths.0', dirname)
            hdf.setValue('title', escape('Just a test'))
            for num in range(1, 15):
                hdf.setValue('items.%d' % (num - 1), escape('Number %d' % num))
            cs = neo_cs.CS(hdf)
            cs.parseFile('template.cs')
            cs.render()
        return render
    except ImportError:
        return None

def kid(dirname):
    try:
        import kid
        kid.path = kid.TemplatePath([dirname])
        template = kid.Template(file='template.kid')
        def render():
            template = kid.Template(file='template.kid',
                                    title='Just a test',
                                    items=['Number %d' % num for num in range(1, 15)])
            template.serialize(output='xhtml')
        return render
    except ImportError:
        return None

def nevow(dirname):
    # FIXME: can't figure out the API
    try:
        from nevow.loaders import xmlfile
        template = xmlfile('template.xml', templateDir=dirname).load()
        def render():
            print template
        return render
    except ImportError:
        return None

def main(engines):
    basepath = os.path.abspath(os.path.dirname(__file__))
    for engine in engines:
        dirname = os.path.join(basepath, engine)
        print '%s:' % engine.capitalize()
        t = timeit.Timer(setup='from __main__ import %s; render = %s("%s")'
                               % (engine, engine, dirname),
                         stmt='render()')
        print '%.2f ms' % (1000 * t.timeit(number=1000) / 1000)

if __name__ == '__main__':
    engines = [arg for arg in sys.argv[1:] if arg[0] != '-']

    if '-p' in sys.argv:
        import hotshot, hotshot.stats
        prof = hotshot.Profile("template.prof")
        benchtime = prof.runcall(main, engines)
        stats = hotshot.stats.load("template.prof")
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats()
    else:
        main(engines)
