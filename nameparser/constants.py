# -*- coding: utf-8 -*-
import re

re_spaces = re.compile(r"\s+")
re_word = re.compile(r"\w+")
re_mac = re.compile(r'^(ma?c)(\w)', re.I)
re_initial = re.compile(r'^(\w\.|[A-Z])?$')

TITLES = set([
    'dr','doctor','miss','misses','mr','mister','mrs','ms','sir',
    'rev','madam','madame','ab','2ndlt','amn','1stlt','a1c','capt','sra','maj',
    'ssgt','ltcol','tsgt','col','briggen','1stsgt','majgen','smsgt','ltgen',
    '1stsgt','gen','cmsgt','1stsgt','ccmsgt','cmsaf','pvt','2lt','pv2','1lt',
    'pfc','cpt','spc','maj','cpl','ltc','sgt','col','ssg','bg','sfc','mg',
    'msg','ltg','1sgt','gen','sgm','csm','sma','wo1','wo2','wo3','wo4','wo5',
    'ens','sa','ltjg','sn','lt','po3','lcdr','po2','cdr','po1','capt','cpo',
    'radm(lh)','scpo','radm(uh)','mcpo','vadm','mcpoc','adm','mpco-cg','cwo-2',
    'cwo-3','cwo-4','pvt','2ndlt','pfc','1stlt','lcpl','capt','cpl','maj','sgt',
    'ltcol','ssgt','col','gysgt','bgen','msgt','majgen','1stsgt','ltgen','mgysgt',
    'gen','sgtmaj','sgtmajmc','wo-1','cwo-2','cwo-3','cwo-4','cwo-5','ens','sa',
    'ltjg','sn','lt','po3','lcdr','po2','cdr','po1','capt','cpo','rdml','scpo',
    'radm','mcpo','vadm','mcpon','adm','fadm','wo1','cwo2','cwo3','cwo4','cwo5'
])

# QUESTIONABLE_TITLES could be last names or they could be titles.
# TODO: need to find best way to deal with these, not doing anything special yet.
# http://code.google.com/p/python-nameparser/issues/detail?id=3
QUESTIONABLE_TITLES = ('judge',)

# PUNC_TITLES could be names or titles, but if they have period at the end they're a title
PUNC_TITLES = ('hon.',)

# words that prefix last names. Can be chained like "de la Vega"
PREFICES = set([
    'abu','bon','ben','bin','da','dal','de','del','der','de','di',u'dí','e','ibn',
    'la','le','san','st','ste','van','vel','von'
])
SUFFICES = set([
    'esq','esquire','jr','sr','2','i','ii','iii','iv','v','clu','chfc',
    'cfp','md','phd'
])
CAPITALIZATION_EXCEPTIONS = (
    ('ii' ,'II'),
    ('iii','III'),
    ('iv' ,'IV'),
    ('md' ,'M.D.'),
    ('phd','Ph.D.'),
)
CONJUNCTIONS = set(['&', 'and', 'et', 'e', 'und', 'y'])

