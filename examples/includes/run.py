#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import os
import sys
import timing

from markup.template import Context, TemplateLoader

def test():
    base_path = os.path.dirname(os.path.abspath(__file__))
    loader = TemplateLoader([os.path.join(base_path, 'skins'),
                             os.path.join(base_path, 'module'),
                             os.path.join(base_path, 'common')])

    timing.start()
    tmpl = loader.load('test.html')
    timing.finish()
    print ' --> parse stage: %dms' % timing.milli()

    data = dict(hello='<world>', skin='default', hey='ZYX', bozz=None,
                items=['Number %d' % num for num in range(1, 15)])

    print tmpl.generate(Context(**data)).render(method='html')

    times = []
    for i in range(100):
        timing.start()
        list(tmpl.generate(Context(**data)))
        timing.finish()
        sys.stdout.write('.')
        sys.stdout.flush()
        times.append(timing.milli())
    print

    print ' --> render stage: %dms (avg), %dms (min), %dms (max)' % (
          sum(times) / len(times), min(times), max(times))

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
