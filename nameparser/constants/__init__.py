# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import collections

from nameparser.constants.prefixes import PREFIXES
from nameparser.constants.capitalization import CAPITALIZATION_EXCEPTIONS
from nameparser.constants.conjunctions import CONJUNCTIONS
from nameparser.constants.suffixes import SUFFIXES
from nameparser.constants.titles import TITLES
from nameparser.constants.titles import FIRST_NAME_TITLES
from nameparser.constants.regexes import REGEXES

class Manager(collections.Set):
    def __init__(self, elements):
        self.elements = elements
    
    def __call__(self):
        return self.elements
    
    def __iter__(self):
        return self.elements
    
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
        [self.elements.add(s.lower().replace('.','')) for s in strings]
        return self.elements
    
    def remove(self, *strings):
        [self.elements.remove(s) for s in strings if s in self.elements]
        return self.elements

class Constants(object):
    
    prefixes                    = Manager(PREFIXES)
    suffixes                    = Manager(SUFFIXES)
    titles                      = Manager(TITLES)
    first_name_titles           = Manager(FIRST_NAME_TITLES)
    conjunctions                = Manager(CONJUNCTIONS)
    regexes                     = Manager(REGEXES)
    suffixes_prefixes_titles    = Manager(PREFIXES | SUFFIXES | TITLES)
    
    # these arent strings so Manager isn't helpful
    capitalization_exceptions   = CAPITALIZATION_EXCEPTIONS


class Regexes(object):
    def __init__(self):
        for name, re in REGEXES:
            setattr(self, name, re)

constants = Constants()
regexes = Regexes()
