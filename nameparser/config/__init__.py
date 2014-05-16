# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import collections

from nameparser.util import lc
from nameparser.config.prefixes import PREFIXES
from nameparser.config.capitalization import CAPITALIZATION_EXCEPTIONS
from nameparser.config.conjunctions import CONJUNCTIONS
from nameparser.config.suffixes import SUFFIXES
from nameparser.config.titles import TITLES
from nameparser.config.titles import FIRST_NAME_TITLES
from nameparser.config.regexes import REGEXES

class SetManager(collections.Set):
    '''
    Easily add and remove config variables per module or instance.
    
    Only special functionality beyond that provided by set() is
    to normalize constants for comparison (lower case, no periods)
    when they are add()ed and remove()d and allow passing multiple 
    string arguments to the add() and remove() methods.
    '''
    def __init__(self, elements):
        self.elements = set(elements)
    
    def __call__(self):
        return self.elements
    
    def __iter__(self):
        return iter(self.elements)
    
    def __contains__(self, value):
        return value in self.elements
    
    def __len__(self):
        return len(self.elements)
    
    def next(self):
        return self.__next__()

    def __next__(self):
        if self.count >= len(self.elements):
            self.count = 0
            raise StopIteration
        else:
            c = self.count
            self.count = c + 1
            return getattr(self, self.elements[c]) or next(self)
    
    def add(self, *strings):
        [self.elements.add(lc(s)) for s in strings]
        return self.elements
    
    def remove(self, *strings):
        [self.elements.remove(lc(s)) for s in strings if lc(s) in self.elements]
        return self.elements


class TupleManager(dict):
    '''
    aka, dotdict. Change the tuple into a slightly more friendly dictionary with 
    dot.notation access.
    '''
    def __getattr__(self, attr):
        return self.get(attr)
    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__


class Constants(object):
    
    def __init__(self):
        self.prefixes          = SetManager(PREFIXES)
        self.suffixes          = SetManager(SUFFIXES)
        self.titles            = SetManager(TITLES)
        self.first_name_titles = SetManager(FIRST_NAME_TITLES)
        self.conjunctions      = SetManager(CONJUNCTIONS)
        self.capitalization_exceptions = TupleManager(CAPITALIZATION_EXCEPTIONS)
        self.RE                = TupleManager(REGEXES)
    
    @property
    def suffixes_prefixes_titles(self):
        return self.prefixes | self.suffixes | self.titles
    

# provide a common instance for the module to share
# so its adjust configuration for the entire module.
constants = Constants()
