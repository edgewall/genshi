
import unittest

from genshi.core import START, QName
from genshi.path import Path
from genshi.template.match import MatchSet

class MatchSetTestCase(unittest.TestCase):

    def make_template(self, path):
            
        template = (path.test(ignore_context=True),
                    path, [], set(), [], [])
        return template

    def make_tag_event(self, tag):
        return (START, (QName(unicode(tag)), None), 0)
    
    def test_simple_match(self):

        m = MatchSet()
        t1 = self.make_template(Path("tag"))
        m.add(t1)
        
        t2 = self.make_template(Path("tag2"))
        m.add(t2)

        result = m.find_matches(self.make_tag_event("tag"))

        assert t1 in result
        assert t2 not in result

    def test_after(self):

        m = MatchSet()
        t1 = self.make_template(Path("tag"))
        m.add(t1)
        t2 = self.make_template(Path("tag2"))
        m.add(t2)

        m2 = m.after_template(t1)

        result = m2.find_matches(self.make_tag_event("tag"))
        
        assert t1 not in result

        result = m2.find_matches(self.make_tag_event("tag2"))

        assert t2 in result
        
    def test_before_exclusive(self):

        m = MatchSet()
        t1 = self.make_template(Path("tag"))
        m.add(t1)
        t2 = self.make_template(Path("tag2"))
        m.add(t2)

        m2 = m.before_template(t2, False)

        result = m2.find_matches(self.make_tag_event("tag2"))

        assert t2 not in result

        result = m2.find_matches(self.make_tag_event("tag"))
        
        assert t1 in result
        
        m3 = m.before_template(t1, False)

        assert not m3
        
        result = m3.find_matches(self.make_tag_event("tag"))
        
        assert t1 not in result

        
    def test_before_inclusive(self):

        m = MatchSet()
        t1 = self.make_template(Path("tag"))
        m.add(t1)
        t2 = self.make_template(Path("tag2"))
        m.add(t2)

        t3 = self.make_template(Path("tag3"))
        m.add(t3)

        m2 = m.before_template(t2, True)

        result = m2.find_matches(self.make_tag_event("tag2"))

        assert t2 in result

        result = m2.find_matches(self.make_tag_event("tag"))

        assert t1 in result

    def test_remove(self):

        m = MatchSet()
        t1 = self.make_template(Path("tag"))
        m.add(t1)
        t2 = self.make_template(Path("tag2"))
        m.add(t2)

        m.remove(t1)

        result = m.find_matches(self.make_tag_event("tag"))

        assert t1 not in result

        result = m.find_matches(self.make_tag_event("tag2"))

        assert t2 in result

    def test_empty_range(self):
        m = MatchSet()
        t1 = self.make_template(Path("tag"))
        m.add(t1)
        t2 = self.make_template(Path("tag2"))
        m.add(t2)

        m2 = m.after_template(t1)
        m3 = m2.before_template(t2, False)

        assert not m3


        
        
              
def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MatchSetTestCase, 'test'))
    return suite

test_suite = suite()
if __name__ == '__main__':
    unittest.main(defaultTest='suite')

