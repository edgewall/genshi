# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Various utility classes and functions."""


class LRUCache(dict):
    """A dictionary-like object that stores only a certain number of items, and
    discards its least recently used item when full.
    
    >>> cache = LRUCache(3)
    >>> cache['A'] = 0
    >>> cache['B'] = 1
    >>> cache['C'] = 2
    >>> len(cache)
    3
    
    >>> cache['A']
    0
    
    Adding new items to the cache does not increase its size. Instead, the least
    recently used item is dropped:
    
    >>> cache['D'] = 3
    >>> len(cache)
    3
    >>> 'B' in cache
    False
    
    Iterating over the cache returns the keys, starting with the most recently
    used:
    
    >>> for key in cache:
    ...     print key
    D
    A
    C

    This code is based on the LRUCache class from ``myghtyutils.util``, written
    by Mike Bayer and released under the MIT license. See:

      http://svn.myghty.org/myghtyutils/trunk/lib/myghtyutils/util.py
    """

    class _Item(object):
        def __init__(self, key, value):
            self.previous = self.next = None
            self.key = key
            self.value = value
        def __repr__(self):
            return repr(self.value)

    def __init__(self, capacity):
        self._dict = dict()
        self.capacity = capacity
        self.head = None
        self.tail = None

    def __contains__(self, key):
        return key in self._dict

    def __iter__(self):
        cur = self.head
        while cur:
            yield cur.key
            cur = cur.next

    def __len__(self):
        return len(self._dict)

    def __getitem__(self, key):
        item = self._dict[key]
        self._update_item(item)
        return item.value

    def __setitem__(self, key, value):
        item = self._dict.get(key)
        if item is None:
            item = self._Item(key, value)
            self._dict[key] = item
            self._insert_item(item)
        else:
            item.value = value
            self._update_item(item)
            self._manage_size()

    def __repr__(self):
        return repr(self._dict)

    def _insert_item(self, item):
        item.previous = None
        item.next = self.head
        if self.head is not None:
            self.head.previous = item
        else:
            self.tail = item
        self.head = item
        self._manage_size()

    def _manage_size(self):
        while len(self._dict) > self.capacity:
            olditem = self._dict[self.tail.key]
            del self._dict[self.tail.key]
            if self.tail != self.head:
                self.tail = self.tail.previous
                self.tail.next = None
            else:
                self.head = self.tail = None

    def _update_item(self, item):
        if self.head == item:
            return

        previous = item.previous
        previous.next = item.next
        if item.next is not None:
            item.next.previous = previous
        else:
            self.tail = previous

        item.previous = None
        item.next = self.head
        self.head.previous = self.head = item


def flatten(items):
    """Flattens a potentially nested sequence into a flat list:
    
    >>> flatten((1, 2))
    [1, 2]
    >>> flatten([1, (2, 3), 4])
    [1, 2, 3, 4]
    >>> flatten([1, (2, [3, 4]), 5])
    [1, 2, 3, 4, 5]
    """
    retval = []
    for item in items:
        if isinstance(item, (list, tuple)):
            retval += flatten(item)
        else:
            retval.append(item)
    return retval
