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

class Manager(collections.Set):
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

class Constants(object):
    
    def __init__(self):
        self.prefixes          = Manager(PREFIXES)
        self.suffixes          = Manager(SUFFIXES)
        self.titles            = Manager(TITLES)
        self.first_name_titles = Manager(FIRST_NAME_TITLES)
        self.conjunctions      = Manager(CONJUNCTIONS)
        self.regexes           = Manager(REGEXES)
    
    @property
    def suffixes_prefixes_titles(self):
        return self.prefixes | self.suffixes | self.titles
    
    # these arent strings so Manager isn't helpful
    capitalization_exceptions = CAPITALIZATION_EXCEPTIONS
    

class Regexes(object):
    def __init__(self):
        for name, re in REGEXES:
            setattr(self, name, re)

constants = Constants()
regexes = Regexes()
