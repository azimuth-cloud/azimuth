"""
Generic utilities used by the JASMIN portal
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from functools import reduce
from collections import Iterable


def getattrs(obj, attrs, default):
    """
    Similar to `getattr`, but `attrs` is an array of attribute names to be
    resolved in a chained manner
    
    If an attribute cannot be resolved at any point in the chain, default is returned
    """
    try:
        return reduce(getattr, attrs, obj)
    except (KeyError, AttributeError):
        return default
    
    
class DeferredIterable(Iterable):
    """
    Iterable wrapper where the creation of the underlying iterable is deferred
    until data is first requested
    """
    def __init__(self, factory):
        self._factory = factory
        self._underlying = None
        
    def __iter__(self):
        if self._underlying is None:
            self._underlying = self._factory()
            self._factory = None
        return iter(self._underlying)
    