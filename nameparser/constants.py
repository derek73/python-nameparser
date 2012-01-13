import re

re_spaces = re.compile(r"\s+")
re_word = re.compile(r"\w+")
re_mac = re.compile(r'^(ma?c)(\w)', re.I)
re_initial = re.compile(r'^(\w\.|[A-Z])?$')

TITLES = set([
    'dr','doctor','miss','misses','mr','mister','mrs','ms','sir',
    'rev','madam','madame','AB','2ndLt','Amn','1stLt','A1C','Capt','SrA','Maj',
    'SSgt','LtCol','TSgt','Col','BrigGen','1stSgt','MajGen','SMSgt','LtGen',
    '1stSgt','Gen','CMSgt','1stSgt','CCMSgt','CMSAF','PVT','2LT','PV2','1LT',
    'PFC','CPT','SPC','MAJ','CPL','LTC','SGT','COL','SSG','BG','SFC','MG',
    'MSG','LTG','1SGT','GEN','SGM','CSM','SMA','WO1','WO2','WO3','WO4','WO5',
    'ENS','SA','LTJG','SN','LT','PO3','LCDR','PO2','CDR','PO1','CAPT','CPO',
    'RADM(LH)','SCPO','RADM(UH)','MCPO','VADM','MCPOC','ADM','MPCO-CG','CWO-2',
    'CWO-3','CWO-4','Pvt','2ndLt','PFC','1stLt','LCpl','Capt','Cpl','Maj','Sgt',
    'LtCol','SSgt','Col','GySgt','BGen','MSgt','MajGen','1stSgt','LtGen','MGySgt',
    'Gen','SgtMaj','SgtMajMC','WO-1','CWO-2','CWO-3','CWO-4','CWO-5','ENS','SA',
    'LTJG','SN','LT','PO3','LCDR','PO2','CDR','PO1','CAPT','CPO','RDML','SCPO',
    'RADM','MCPO','VADM','MCPON','ADM','FADM','WO1','CWO2','CWO3','CWO4','CWO5'
])

# QUESTIONABLE_TITLES could be last names or they could be titles.
# TODO: need to find best way to deal with these, not doing anything special yet.
# http://code.google.com/p/python-nameparser/issues/detail?id=3
QUESTIONABLE_TITLES = ('judge',)

# PUNC_TITLES could be names or titles, but if they have period at the end they're a title
PUNC_TITLES = ('hon.',)
PREFICES = set([
    'abu','bon','ben','bin','da','dal','de','del','der','de','di','e','ibn',
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

