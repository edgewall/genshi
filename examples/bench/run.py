from cgi import escape
from datetime import datetime, timedelta
import os
import sys

def markup(dirname):
    from markup.template import Context, TemplateLoader
    loader = TemplateLoader([dirname], False)
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

def main():
    basepath = os.path.abspath(os.path.dirname(__file__))
    for engine in ('markup', 'clearsilver', 'kid'):
        dirname = os.path.join(basepath, engine)
        print '%s:' % engine.capitalize()
        func = globals()[engine](dirname)
        if not func:
            print 'Skipping %s, not installed?' % engine.capitalize()
            continue
        times = []
        for i in range(100):
            start = datetime.now()
            sys.stdout.write('.')
            sys.stdout.flush()
            func()
            times.append(datetime.now() - start)

        print
        total_ms = sum([t.seconds * 1000 + t.microseconds for t in times])
        print ' --> timing: %s (avg), %s (min), %s (max)' % (
              timedelta(microseconds=total_ms / len(times)),
              timedelta(microseconds=min([t.seconds * 1000 + t.microseconds for t in times])),
              timedelta(microseconds=max([t.seconds * 1000 + t.microseconds for t in times])))
        print

if __name__ == '__main__':
    main()
