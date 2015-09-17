"""
This module contains generic utilities and helpers used by the JASMIN portal.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

from functools import reduce
from collections import Iterable


def getattrs(obj, attrs, default):
    """
    Similar to ``getattr``, but allows a list of attribute names to be resolved
    in a chained manner.
    
    If an attribute cannot be resolved at any point in the chain, the default is
    returned.
    
    :param obj: An object to start resolving names from
    :param attrs: List of names to resolve
    :param default: Default value if attribute resolution fails at any stage
    :returns: The value at the end of the chain if resolution is successful,
              otherwise the default
    """
    try:
        return reduce(getattr, attrs, obj)
    except (KeyError, AttributeError):
        return default
    
    
class DeferredIterable(Iterable):
    """
    Iterable decorator where the creation of the underlying iterable is deferred
    until data is first requested.
    
    :param factory: Callable that creates the underlying iterable. Should take no
                    arguments and return an iterable
    """
    def __init__(self, factory):
        self._factory = factory
        self._underlying = None
        
    def __iter__(self):
        if self._underlying is None:
            self._underlying = self._factory()
            self._factory = None
        return iter(self._underlying)
    