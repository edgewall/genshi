from datetime import datetime, timedelta
import os
import sys

import kid

def test():
    base_path = os.path.dirname(os.path.abspath(__file__))
    kid.path = kid.TemplatePath([os.path.join(base_path, 'common'),
                                 os.path.join(base_path, 'module')])

    ctxt = dict(hello='<world>', hey='ZYX', bozz=None,
                items=['Number %d' % num for num in range(1, 15)],
                prefix='#')

    start = datetime.now()
    template = kid.Template(file='test.kid', **ctxt)
    print ' --> parse stage: ', datetime.now() - start

    times = []
    for i in range(100):
        start = datetime.now()
        for output in template.generate():
            if i == 0:
                sys.stdout.write(output)
        if i == 0:
            print
        else:
            sys.stdout.write('.')
            sys.stdout.flush()
        times.append(datetime.now() - start)
    print

    total_ms = sum([t.seconds * 1000 + t.microseconds for t in times])
    print ' --> render stage: %s (avg), %s (min), %s (max):' % (
          timedelta(microseconds=total_ms / len(times)),
          timedelta(microseconds=min([t.seconds * 1000 + t.microseconds for t in times])),
          timedelta(microseconds=max([t.seconds * 1000 + t.microseconds for t in times])))

if __name__ == '__main__':
    if '-p' in sys.argv:
        import profile, pstats
        profile.run('test()', '.tmpl_prof')
        stats = pstats.Stats('.tmpl_prof')
        stats.strip_dirs().sort_stats('time').print_stats(10)
    else:
        test()
