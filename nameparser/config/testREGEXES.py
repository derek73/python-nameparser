# -*- coding: utf-8 -*-
"""
Created on Thu Mar 18 04:54:12 2021

@author: New User
"""
import re

class TupleManager(dict):
    '''
    A dictionary with dot.notation access. Subclass of ``dict``. Makes the tuple constants 
    more friendly.
    '''
    def __getattr__(self, attr):
        return self.get(attr)
    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__

    def __getstate__(self):
        return dict(self)

    def __setstate__(self, state):
        self.__init__(state)

    def __reduce__(self):
        return (TupleManager, (), self.__getstate__())

REGEXES = [
    ("spaces", re.compile(r"\s+", re.U)),
    ("word", re.compile(r"(\w|\.)+", re.U)),
    ("mac", re.compile(r'^(ma?c)(\w{2,})', re.I | re.U)),
    ("initial", re.compile(r'^(\w\.|[A-Z])?$', re.U)),
    ("quoted_word", re.compile(r'(?<!\w)\'([^\s]*?)\'(?!\w)', re.U), 'nickname'),
    ("double_quotes", re.compile(r'\"(.*?)\"', re.U), 'nickname'),
    ("parenthesis", re.compile(r'\((.*?)\)', re.U), 'nickname'),
    #("quoted_word", re.compile(r'(?<!\w)\'([^\s]*?)\'(?!\w)', re.U)),
    #("double_quotes", re.compile(r'\"(.*?)\"', re.U)),
    #("parenthesis", re.compile(r'\((.*?)\)', re.U)),
    ("roman_numeral", re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I | re.U)),
    ("no_vowels",re.compile(r'^[^aeyiuo]+$', re.I | re.U)),
    ("period_not_at_end",re.compile(r'.*\..+$', re.I | re.U)),
    ("phd", re.compile(r'\s(ph\.?\s+d\.?)', re.I | re.U)),
]

r = TupleManager(tpl[:2] for tpl in REGEXES)
nn_TM = TupleManager(tpl[:2] for tpl in REGEXES if tpl[-1] == 'nickname')
nn = [tpl[1] for tpl in REGEXES if tpl[-1] == 'nickname']

rgx = re.compile(r"(?!\w)‘([^’]*?)’(?!\w)", re.U)
