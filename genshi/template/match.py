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
    """ A MatchSet is a set of matches discovered by the parser. This
    class encapsulates the matching of a particular event to a set of
    matches. It is optimized for basic tag matches, since that is by
    far the most common use of py:match.

    The two primary entry points into MatchSet are ``add``, which adds
    a new py:match, and ``find_matches``, which returns all
    /candidate/ match templates. The consumer of ``find_matches``
    still must call each candidates' match() to ensure the event
    really matches, and to maintain state within the match.

    If a given py:match's path is simply a node name match,
    (LocalNameTest) like "xyz", then MatchSet indexes that in a
    dictionary that maps tag names to matches.

    If the path is more complex like "xyz[k=z]" then then that match
    will always be returned by ``find_matches``.  """
    def __init__(self, parent=None, exclude=None):
        """
        If a parent is given, it means this is a wrapper around another
        set.
        
        If exclude is given, it means include everything in the
        parent, but exclude a specific match template.
        """
        self.parent = parent

        self.current_index = 0

        if parent is None:
            # merely for indexing. Note that this is shared between
            # all MatchSets that share the same root parent. We don't
            # have to worry about exclusions here
            self.match_order = {}
            
            # tag_templates are match templates whose path are simply
            # a tag, like "body" or "img"
            self.tag_templates = {}

            # other_templates include all other match templates, such
            # as ones with complex paths like "[class=container]"
            self.other_templates = []

            # exclude is a list of templates to ignore when iterating
            # through templates
            self.exclude = []
            if exclude is not None:
                self.exclude.append(exclude)
        else:
            # We have a parent: Just copy references to member
            # variables in parent so that there's no performance loss,
            # but make our own exclusion set, so we don't have to
            # chain exclusions across a chain of MatchSets
            self.match_order = parent.match_order
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

        # match_templates are currently tuples that contain unhashable
        # objects. So we'll use id() for now. 
        self.match_order[id(match_template)] = len(self.match_order)
        
        path = match_template[1]

        self.current_index += 1
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

        # clean up match_order
        del self.match_order[id(match_template)]

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
            
    def find_raw_matches(self, event):
        """ Return a list of all valid templates that can be used for the
        given event. Ordering is funky because we first check
        self.tag_templates, then check self.other_templates.
        """
        kind, data, pos = event[:3]

        # todo: get the order right
        if kind is START:
            tag, attrs = data
            if tag.localname in self.tag_templates:
                for template in self.tag_templates[tag.localname]:
                    yield template

        for template in self.other_templates:
            yield template

    def find_matches(self, event):
        """ Return a list of all valid templates that can be used for the
        given event.

        The basic work here is sorting the result of find_raw_matches
        """

        # remove exclusions
        matches = filter(lambda template: template not in self.exclude,
                         self.find_raw_matches(event))

        # sort the results according to the order they were added
        return sorted(matches, key=lambda v: self.match_order[id(v)])

    def __nonzero__(self):
        """
        allow this to behave as a list
        """
        return bool(self.tag_templates or self.other_templates)

    def __str__(self):
        parent = ""
        if self.parent:
            parent = ": child of 0x%x" % id(self.parent)

        exclude = ""
        if self.exclude:
            exclude = " / excluding %d items" % len(self.exclude)
            
        return "<MatchSet 0x%x %d tag templates, %d other templates%s%s>" % (id(self), len(self.tag_templates), len(self.other_templates), parent, exclude)
