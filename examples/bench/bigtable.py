# -*- encoding: utf-8 -*-
# Template language benchmarks
#
# Objective: Generate a 1000x10 HTML table as fast as possible.
#
# Author: Jonas Borgström <jonas@edgewall.com>

import sys
import timeit

import cElementTree as cet
from elementtree import ElementTree as et
import kid
from markup.builder import tag
from markup.template import Context, Template
import neo_cgi
import neo_cs
import neo_util

table = [dict(a=1,b=2,c=3,d=4,e=5,f=6,g=7,h=8,i=9,j=10)
          for x in range(1000)]

markup_tmpl = Template("""
<table xmlns:py="http://markup.edgewall.org/">
<tr py:for="row in table">
<td py:for="c in row.values()" py:content="c"/>
</tr>
</table>
""")

markup_tmpl2 = Template("""
<table xmlns:py="http://markup.edgewall.org/">$table</table>
""")

kid_tmpl = kid.Template("""
<table xmlns:py="http://purl.org/kid/ns#">
<tr py:for="row in table">
<td py:for="c in row.values()" py:content="c"/>
</tr>
</table>
""")

kid_tmpl2 = kid.Template("""
<html xmlns:py="http://purl.org/kid/ns#">$table</html>
""")


def test_markup():
    """Markup template"""
    ctxt = Context(table=table)
    stream = markup_tmpl.generate(ctxt)
    stream.render('html')

def test_markup_builder():
    """Markup template + tag builder"""
    stream = tag.TABLE([
        tag.tr([tag.td(c) for c in row.values()])
        for row in table
    ]).generate()
    ctxt = Context(table=stream)
    stream = markup_tmpl2.generate(ctxt)
    stream.render('html')

def test_builder():
    """Markup tag builder"""
    stream = tag.TABLE([
        tag.tr([
            tag.td(c) for c in row.values()
        ])
        for row in table
    ]).generate()
    stream.render('html')

def test_kid():
    """Kid template"""
    kid_tmpl.table = table
    kid_tmpl.serialize(output='html')

def test_kid_et():
    """Kid template + cElementTree"""
    _table = cet.Element('table')
    for row in table:
        td = cet.SubElement(_table, 'tr')
        for c in row.values():
            cet.SubElement(td, 'td').text=str(c)
    kid_tmpl2.table = _table
    kid_tmpl2.serialize(output='html')

def test_et(): 
    """ElementTree"""
    _table = et.Element('table')
    for row in table:
        tr = et.SubElement(_table, 'tr')
        for c in row.values():
            et.SubElement(tr, 'td').text=str(c)
    et.tostring(_table)
        
def test_cet(): 
    """cElementTree"""
    _table = cet.Element('table')
    for row in table:
        tr = cet.SubElement(_table, 'tr')
        for c in row.values():
            cet.SubElement(tr, 'td').text=str(c)
    cet.tostring(_table)

def test_clearsilver():
    """ClearSilver"""
    hdf = neo_util.HDF()
    for i, row in enumerate(table):
        for j, c in enumerate(row.values()):
            hdf.setValue("rows.%d.cell.%d" % (i, j), str(c))

    cs = neo_cs.CS(hdf)
    cs.parseStr("""
<table><?cs
  each:row=rows
?><tr><?cs each:c=row.cell
  ?><td><?cs var:c ?></td><?cs /each
?></tr><?cs /each?>
</table>""")
    cs.render()


def run(which=None, number=10):
    tests = ['test_builder', 'test_markup', 'test_markup_builder', 'test_kid',
             'test_kid_et', 'test_et', 'test_cet', 'test_clearsilver']
    if which:
        tests = filter(lambda n: n[5:] in which, tests)

    for test in tests:
        t = timeit.Timer(setup='from __main__ import %s;' % test,
                         stmt='%s()' % test)
        time = t.timeit(number=number) / number

        print '%-35s %8.2f ms' % (getattr(sys.modules[__name__], test).__doc__,
                                  1000 * time)


if __name__ == '__main__':
    which = [arg for arg in sys.argv[1:] if arg[0] != '-']

    if '-p' in sys.argv:
        import hotshot, hotshot.stats
        prof = hotshot.Profile("template.prof")
        benchtime = prof.runcall(run, which, number=1)
        stats = hotshot.stats.load("template.prof")
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats()
    else:
        run(which)
