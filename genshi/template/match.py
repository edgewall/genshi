from genshi.core import START
from genshi.path import CHILD, LocalNameTest

from copy import copy

def is_simple_path(path):
    """
    Is the path merely a tag match like "foo"?
    """
    if len(path.paths) == 1 and len(path.paths[0]) == 1:
        axis, nodetest, predicates = path.paths[0][0]
        if (axis is CHILD and
            not predicates and
            isinstance(nodetest, LocalNameTest)):
            return True

    return False


class MatchSet(object):

    def __init__(self, parent=None, exclude=None):
        """
        If a parent is given, it means this is a wrapper around another
        set. Just copy references to member variables in parent, but
        also set exclude
        """
        self.parent = parent
        if parent is None:
            self.tag_templates = {}
            self.other_templates = []
            self.exclude = []
            if exclude is not None:
                self.exclude.append(exclude)
        else:
            self.tag_templates = parent.tag_templates
            self.other_templates = parent.other_templates
            self.exclude = copy(parent.exclude)
            if exclude is not None:
                self.exclude.append(exclude)
    
    def add(self, match_template):
        """
        match_template is a tuple the form
        test, path, template, hints, namespace, directives
        """
        path = match_template[1]
        
        if is_simple_path(path):
            # special cache of tag
            tag_name = path.paths[0][0][1].name
            # setdefault is wasteful
            if tag_name not in self.tag_templates:
                self.tag_templates[tag_name] = [match_template]
            else:
                self.tag_templates[tag_name].append(match_template)
                
        else:
            self.other_templates.append(match_template)

    def remove(self, match_template):
        """
        Permanently remove a match_template - mainly for match_once
        """
        path = match_template[1]
        
        if is_simple_path(path):
            tag_name = path.paths[0][0][1].name
            if tag_name in self.tag_templates:
                template_list = self.tag_templates[tag_name]
                template_list.remove(match_template)
                if not template_list:
                    del self.tag_templates[tag_name]

        else:
            self.other_templates.remove(match_template)

    def single_match(cls, match_template):
        """
        Factory for creating a MatchSet with just one match
        """
        match_set = cls()
        match_set.add(match_template)
        return match_set
    single_match = classmethod(single_match)

    def with_exclusion(self, exclude):
        """
        Factory for creating a MatchSet based on another MatchSet, but
        with certain templates excluded
        """
        cls = self.__class__
        new_match_set = cls(parent=self, exclude=exclude)
        return new_match_set
            
    def find_matches(self, event):
        """
        Return a list of all valid templates that can be used for the given event.
        """
        kind, data, pos = event[:3]

        # todo: get the order right
        if kind is START:
            tag, attrs = data
            if tag.localname in self.tag_templates:
                for template in self.tag_templates[tag.localname]:
                    if template not in self.exclude:
                        yield template

        for template in self.other_templates:
            if template not in self.exclude:
                yield template


    def __nonzero__(self):
        """
        allow this to behave as a list
        """
        return bool(self.tag_templates or self.other_templates)

    def __iter__(self):
        """
        I don't think we really need this, but it lets us behave like a list
        """
        for template_list in self.tag_templates.iteritems():
            for template in template_list:
                yield template
        for template in self.other_templates:
            yield template

    def __str__(self):
        parent = ""
        if self.parent:
            parent = ": child of 0x%x" % id(self.parent)

        exclude = ""
        if self.exclude:
            exclude = " / excluding %d items" % len(self.exclude)
            
        return "<MatchSet 0x%x %d tag templates, %d other templates%s%s>" % (id(self), len(self.tag_templates), len(self.other_templates), parent, exclude)
