from genshi.core import StreamEventKind
from genshi.util import LRUCache

OPTIMIZATION_POSSIBILITY = StreamEventKind("OPTIMIZATION_POSSIBILITY")
OPTIMIZED_FRAGMENT = StreamEventKind("OPTIMIZED_FRAGMENT")

class Optimizer(object):
    """Manages optimized tags with variables bound and filter trees"""
    def __init__(self, size=100):
        self._filtersCount = 1
        self._filters = {0:{}}
        self._fragmentsCount = 0
        self._fragments = {}
        self._data = LRUCache(size)

    def get_filters_child_id(self, fid, filter):
        """Finds filter tree node"""
        try:
            return self._filters[fid][filter]
        except KeyError:
            id_ = self._filtersCount
            self._filters[fid][filter] = id_
            self._filters[id_] = {}
            self._filtersCount += 1
            return id_
    def get_fragment_id(self, *args):
        try:
            return self._fragments[args]
        except KeyError:
            id_ = self._fragmentsCount
            self._fragments[args] = id_
            self._fragmentsCount += 1
            return id_

    @property
    def root_id(self):
        return 0

    def get_cache_for(self, fragmentId, filtersId):
        try:
            return self._data[(filtersId, fragmentId)]
        except KeyError:
            return None

    def set_cache_for(self, fragmentId, filtersId, stream):
        self._data[(filtersId, fragmentId,)] = stream


class OptimizedFragment(object):
    def __init__(self, stream, optimizer, fragmentId, filtersId=None):
        self._stream = stream
        self.fragmentId = fragmentId
        if filtersId is None:
            self.filtersId = optimizer.root_id
        else:
            self.filtersId = filtersId
        self.optimizer = optimizer
    def get_stream(self):
        """Returns stream. Only for embedding in generators, if something
        more needed use process_stream"""
        return self._stream
    def process_stream(self):
        """Renders it in place and asks to save in cache"""
        s = self.optimizer.get_cache_for(self.fragmentId, self.filtersId)
        if s is None:
            s = list(self._stream)
            self.optimizer.set_cache_for(self.fragmentId, self.filtersId, s)
        self._stream = s
        return self._stream
    def create_child(self, filter, stream):
        """Create child fragment (representing fragment after applying filter)"""
        filtersId = self.optimizer.get_filters_child_id(self.filtersId, filter)
        #print "Creating child", filter
        return OptimizedFragment(stream, self.optimizer, self.fragmentId,
                                 filtersId)

def optimized_flatten(stream):
    for event in stream:
        if event[0] is OPTIMIZED_FRAGMENT:
            for e in optimized_flatten(event[1].process_stream()):
                yield e
        else:
            yield event
