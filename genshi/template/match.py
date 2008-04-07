from genshi.core import START
from genshi.path import CHILD, LocalNameTest

from copy import copy
from itertools import ifilter

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

class MatchState(object):
    """ This is a container for all py:match's found during parsing. It
    does not provide a way to slice and dice which templates
    match. The main interfaces are ``add``, ``remove``, and
    ``find_raw_matches``

    this class maintains a hash, ``self.match_order`` which maps a
    template to its order, to make sure that events can be returned in
    order

    """
    def __init__(self):
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

        self.current_index = 0

    def add(self, match_template):
        """
        Add a template to the match state
        """
        # match_templates are currently tuples that contain unhashable
        # objects. So we'll use id() for now. 
        self.match_order[id(match_template)] = self.current_index
        self.current_index += 1
        
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
        Remove the template permanently 
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
    will always be returned by ``find_matches``.

    """
    def __init__(self, parent=None,
                 min_index=None,
                 max_index=None):
        """ If a parent is given, it means this is likely a MatchSet
        constrained by min_index or max_index.
        
        """
        if parent is None:
            self.state = MatchState()
            self.min_index = None
            self.max_index = None
        else:
            # We have a parent: Just copy references to member
            # variables in parent so that there's no performance loss
            self.state = parent.state
            self.max_index = parent.max_index
            self.min_index = parent.min_index
            
        # sub-MatchSets can only be further constrained, not expanded
        if max_index is not None:
            assert self.max_index is None or max_index <= self.max_index
            self.max_index = max_index

        if min_index is not None:
            assert self.min_index is None or min_index > self.min_index
            self.min_index = min_index

        # initialize empty state
        self.not_empty = self.have_matches()
        
    def add(self, match_template):
        """
        match_template is a tuple the form
        test, path, template, hints, namespace, directives
        """
        self.state.add(match_template)
        self.not_empty = self.have_matches()

        # we should never add a new py:match to a constrained
        # MatchSet, therefore the set should never be empty here
        assert self.not_empty

    def remove(self, match_template):
        """
        Permanently remove a match_template - mainly for match_once
        """
        self.state.remove(match_template)
        self.not_empty = self.have_matches()

    def before_template(self, match_template, inclusive):
        """ Return a new MatchSet where only the templates that were declared
        before ``match_template`` are available. If ``inclusive`` is
        true, then it will also include match_template itself.
        
        """
        cls = type(self)
        max_index = self.state.match_order[id(match_template)]
        if not inclusive:
            max_index -= 1
        return cls(parent=self, max_index=max_index)
    
    def after_template(self, match_template):
        """
        Factory for creating a MatchSet that only matches templates after
        the given match
        """
        cls = type(self)
        min_index = self.state.match_order[id(match_template)] + 1
        return cls(parent=self, min_index=min_index)
    

    def find_matches(self, event):
        """ Return a list of all valid templates that can be used for the
        given event.

        The basic work here is sorting the result of find_raw_matches.
        
        """
        # remove exclusions
        def can_match(template):
            # make sure that 
            if (self.min_index is not None and
                self.state.match_order[id(template)] < self.min_index):
                return False

            if (self.max_index is not None and 
                self.state.match_order[id(template)] > self.max_index):
                return False

            return True
        
        matches = ifilter(can_match,
                          self.state.find_raw_matches(event))

        # sort the results according to the order they were added
        return sorted(matches, key=lambda v: self.state.match_order[id(v)])

    def __nonzero__(self):
        """ allow this to behave as a list - and at least try to act empty if
        the list is likely to be empty.
        
        """
        return self.not_empty

    def have_matches(self):
        """ This function does some O(1) checks for states when this MatchSet
        absolutely must be empty - such as when there are no py:match
        templates, or when the max/min index would prohibit any
        possible match.

        This function should be called whenever the match state is
        updated (i.e. any time we add/remove a new py:match, create a
        new MatchSet, etc.)  The expectation is that these
        less-frequent checks are, amortized over a template, are
        cheaper than calls to find_matches() for any arbitrary path.
        
        """
        # dirt-simple case: no py:match templates at all
        if not (self.state.tag_templates or self.state.other_templates):
            return False
        
        # this is easy - before the first element there is nothing
        if (self.max_index is not None and
            self.max_index < 0):
            return False

        # we're constrained, but we've removed any templates after min_index
        if (self.min_index is not None and
            self.min_index > self.state.current_index):
            return False

        # check for a range that is completely constrained
        if self.min_index is not None and self.max_index is not None:
            if self.min_index >= self.max_index:
                return False

        # there might be other cases here, but it's safer to just
        # return True if we can't guess any better
        return True

    def __str__(self):
        parent = ""
        if self.parent:
            parent = ": child of 0x%x" % id(self.parent)

        return "<MatchSet 0x%x %s%d tag templates, %d other templates, range=[%s:%s]%s>" % (
            id(self), self.not_empty and "" or "[empty] ",
            len(self.state.tag_templates), len(self.other_templates),
            self.min_index, self.max_index,
            parent)
