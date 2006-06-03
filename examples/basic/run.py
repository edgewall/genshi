#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import os
import sys

from markup.template import Context, TemplateLoader

def test():
    base_path = os.path.dirname(os.path.abspath(__file__))
    loader = TemplateLoader([os.path.join(base_path, 'common'),
                             os.path.join(base_path, 'module')],
                            auto_reload=True)

    start = datetime.now()
    tmpl = loader.load('test.html')
    print ' --> parse stage: ', datetime.now() - start

    ctxt = Context(hello='<world>', skin='default', hey='ZYX', bozz=None,
                   items=['Number %d' % num for num in range(1, 15)],
                   prefix='#')

    print tmpl.generate(ctxt).render(method='html')

    times = []
    for i in range(100):
        start = datetime.now()
        list(tmpl.generate(ctxt))
        sys.stdout.write('.')
        sys.stdout.flush()
        times.append(datetime.now() - start)
    print

    total_ms = sum([t.seconds * 1000 + t.microseconds for t in times])
    print ' --> render stage: %s (avg), %s (min), %s (max)' % (
          timedelta(microseconds=total_ms / len(times)),
          timedelta(microseconds=min([t.seconds * 1000 + t.microseconds for t in times])),
          timedelta(microseconds=max([t.seconds * 1000 + t.microseconds for t in times])))

if __name__ == '__main__':
    if '-p' in sys.argv:
        import hotshot, hotshot.stats
        prof = hotshot.Profile("template.prof")
        benchtime = prof.runcall(test)
        stats = hotshot.stats.load("template.prof")
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats()
    else:
        test()
