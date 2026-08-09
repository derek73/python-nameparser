from nameparser.config._invariants import assert_normalized

SUFFIX_WORDS = frozenset({
    # #269: Cyrillic мл/ст (junior/senior, the jr/sr analogs) deferred
    # pending the within-script collision vetting the issue asks for;
    # 'ст' especially is a plausible false-positive risk (many two-
    # letter Cyrillic abbreviations exist), and both are short enough
    # to worry about. Not shipped in this pass.
    'dr',
    'esq',
    'esquire',
    'jr',
    'jnr',
    'junior',
    'sr',
    'snr',
    '2',
    'i',
    'ii',
    'iii',
    'iv',
    'v',
    # Bare, not '(ret)'/'(vet)': moved here from literal parenthesized
    # entries in SUFFIX_ACRONYMS. parse_nicknames()'s handle_match() now
    # strips parens/quotes before this set is consulted, so the bare form
    # is correct -- do not re-add the parenthesized form, that would
    # silently reintroduce the #111 bug (parenthesized "(Ret)" matching
    # literally instead of going through nickname/suffix disambiguation).
    'ret',
    'vet',

    # #269 follow-up: Hebrew post-nominals, both gershayim spellings
    # (ASCII '"' and U+05F4); the mid-word quote is inert in
    # extraction, like the ד"ר title. Neither is ever a name.
    'ז"ל',      # "of blessed memory" (deceased), ASCII quote
    'ז״ל',      # same, U+05F4 gershayim
    'שליט"א',   # honorific for a living rabbi, ASCII quote
    'שליט״א',   # same, U+05F4 gershayim

    # #307/#308: CJK postnominal honorifics and degrees. Matched
    # whole-token here, which reaches the SPACED forms; the GLUED
    # forms (田中さん, 김민준씨) are reached by the peel #308 adds to
    # _pipeline/_script_segment.py: it splits a listed tail off the
    # last name token and hands the piece back to this vocabulary --
    # so every GLUED_HONORIFICS entry below is also an entry here,
    # asserted at the foot of this module.
    # Self-selecting like the Korean surnames: a Han, kana or hangul
    # entry can only ever match CJK text. Vetting per the мл/ст
    # standard above, and note the two bars are different -- an entry
    # can be safe in the spaced position and unsafe glued, never the
    # other way round, because the spaced position is a token boundary
    # its writer drew:
    # - 氏: a rare Japanese surname reading exists, but a bare
    #   trailing 氏 after a name is the news-style honorific, and a
    #   氏-surnamed person writes it FIRST.
    # - 양/군: 양 is also a top-tier surname (Yang) -- but a surname
    #   LEADS, so the trailing-only suffix gate never sees it there
    #   (양 미선 keeps family 양); as single-syllable GIVEN names in
    #   final position both are vanishingly rare in practice.
    # - 博士: an attested Japanese given name (ひろし, Hiroshi) --
    #   the doctorate reading vastly dominates the spaced trailing
    #   position this set matches.
    # - 殿: some ninety Japanese surnames end in it (鵜殿, 真殿), which
    #   is what keeps it out of GLUED_HONORIFICS below -- but the
    #   surname-LEADS argument that clears 양/군 clears it here too.
    # - 님: a single hangul syllable, the risk class 양/군 are in, but
    #   it has no hanja reading at all, so it cannot sit inside a
    #   Sino-Korean given name.
    # Bare hangul 선생/교수 are deliberately absent (only the -님
    # honorific forms ship): the bare forms read as common nouns as
    # readily as address terms. 박사 is the exception among the three,
    # shipping bare as well as with -님, because it names a degree
    # rather than a role -- but all three -님 forms ship together
    # (선생님, 교수님, 박사님 are the standard professional honorifics,
    # and shipping two of the three was an oversight). Further
    # candidates (여사, 太太) wait on the same case-by-case argument.
    '씨',        # ko Mr./Ms. -- standardly spaced in Korean orthography
    '박사',      # ko doctorate holder ("Dr.")
    '박사님',    # ko the same, honorific form
    '선생님',    # ko teacher/respected elder
    '교수님',    # ko professor (honorific form)
    '군',        # ko young man ("Master")
    '양',        # ko young woman ("Miss")
    '님',        # ko -- the bare honorific of online/formal address
    '先生',      # zh Mr. / ja teacher-master -- honorific in both
    '女士',      # zh Ms./Madam
    '小姐',      # zh Miss
    '博士',      # zh+ja doctorate holder, shared Han
    '教授',      # zh+ja professor, shared Han
    '様',        # ja formal Mr./Ms. (the mail-addressing honorific)
    '氏',        # ja news-style Mr. (田中氏)
    '殿',        # ja formal, official/rank-flavored
    'さん',      # ja the everyday honorific, kana
    'さま',      # ja the kana spelling of 様
    'くん',      # ja the kana spelling of 君
    'ちゃん',    # ja familiar/diminutive
})
"""

Post-nominal suffixes matched as WORDS: the lookup uses the normalized token,
so only EDGE periods come off and interior ones survive -- "Junior." matches
here, "J.u.n.i.o.r." does not. :data:`SUFFIX_ACRONYMS` is the set matched
with every period removed, so it alone covers the multi-dot spelling
"E.S.Q." -- and, having no interior period to lose, "Esq" as well. 'esq'
is listed here too (v1 data): inert against the shipped acronym set, since
dropping it changes no parse, but what keeps "Esq" matching for a caller
who removes it from :data:`SUFFIX_ACRONYMS`. That is why the two sets are
deliberately not asserted disjoint -- see the guard block at the bottom.

"""
GLUED_HONORIFICS = frozenset({
    # #308: the entries above that may also be peeled off the END of a
    # name token -- 田中さん, 山田太郎様, 김민준씨. A separate set, not
    # SUFFIX_WORDS reused, because the glued position has no token
    # boundary to lean on: the vetting question is not "is this a
    # name?" but "can this END a name?", and only entries that can
    # never end one belong here.
    # kana -- name-final never, in any of the four, and the kana/kanji
    # split is itself a vetting result: くん ships where 君 cannot,
    # since 王君 is a complete Chinese name while the hiragana spelling
    # is unavailable to Chinese at all. Scoped to Chinese on purpose --
    # hiragana of course spells Japanese GIVEN names (高橋みなみ is one,
    # pinned in the case table), which is why the four entries above
    # are vetted one at a time as never name-FINAL rather than waved
    # through as kana.
    'さん', 'さま', 'くん', 'ちゃん',
    # Han -- two-character honorifics with no name-final reading in
    # either language, plus 様. 殿 is deliberately absent though it
    # ships spaced above; see the exclusions below.
    '様', '先生', '教授', '女士', '小姐',
    # hangul -- the -님 compounds too: longest-first peels 선생님 off
    # 김선생님 whole, rather than leaving 김선생 to segment into a
    # family 김 and a given 선생, and 박사님 off 김민준박사님 rather
    # than stranding 박사 in the given name. 박사 is safe glued where
    # its Han twin 博士 is not: that collision is Japanese (博士 =
    # ひろし) and the hangul spelling carries none of it.
    '씨', '님', '선생님', '교수님', '박사', '박사님',
})
"""

The subset of :data:`SUFFIX_WORDS` a name token may end WITH, peeled off as
its own token before segmentation (#308). Deliberately harsher than the
spaced set, because a glued tail has no writer-drawn token boundary to lean
on -- these entries are recognized in the SPACED position only:

* 양, 군 -- 김지양 and 김지군 are given names ending in these syllables, and
  양 is a top-tier surname besides.
* 氏 -- 王氏 is a historical name form ("the Wang woman").
* 博士 -- glued 田中博士 IS Tanaka Hiroshi, an attested given name.
* 殿 -- some ninety Japanese surnames END in it, 鵜殿 (Udono) and 真殿
  (Madono) with four-figure populations, so peeling it would cut a real
  family name in two. Spaced 殿 is safe for the reason 양/군 are: a
  殿-surnamed person's name LEADS, and the suffix gate is trailing-only.

Three more are in NEITHER set, so neither spelling is recognized. 君: 王君 is
a complete Chinese name (君 is a common given-name final), so the honorific
reading never gets the benefit of the doubt -- while its kana spelling くん
ships glued, above. Bare 선생 and 교수: they read as common nouns as readily
as address terms, and only their -님 forms ship.

"""
SUFFIX_ACRONYMS_AMBIGUOUS = frozenset({
    # Suffix acronyms that also commonly work as given-name nicknames on
    # their own (e.g. "Ed", "JD"). Read only by HumanName.parse_nicknames()
    # when deciding whether parenthesized/quoted content is a nickname or a
    # suffix -- content matching one of these stays a nickname rather than
    # being reclassified as a suffix, since that's the more common reading
    # in ambiguous, delimiter-only context.
    #
    # When adding a new entry to SUFFIX_ACRONYMS, also add it here only if
    # the exact letter sequence could plausibly be someone's name on its
    # own -- a given name or nickname (e.g. 'jd', 'ed') or a common
    # surname (e.g. 'ma', 'do'). Unambiguous certifications/degrees
    # (e.g. 'mba', 'cpa', 'phd') don't need an entry. In 2.0 this set
    # also gates bare recognition: an ambiguous acronym counts as a
    # suffix only when written with periods ('M.A.' yes, 'Ma' no), so
    # 'Jack Ma' keeps its family name.
    'do',
    'ed',
    'jd',
    'ma',
})
"""

Acronym suffixes from SUFFIX_ACRONYMS that also plausibly collide with a
common given-name nickname. Not a partition of SUFFIX_ACRONYMS -- a small,
standalone exception list consulted only by parse_nicknames().

"""
SUFFIX_ACRONYMS = frozenset({
    '8-vsb',
    'aas',
    'aba',
    'abc',
    'abd',
    'abpp',
    'abr',
    'aca',
    'acas',
    'ace',
    'acha',
    'acp',
    'ae',
    'ae',
    'aem',
    'afasma',
    'afc',
    'afc',
    'afm',
    'afm',
    'agsf',
    'aia',
    'aicp',
    'ala',
    'alc',
    'alp',
    'am',
    'amd',
    'ame',
    'amieee',
    'ams',
    'aphr',
    'apn',
    'aprn',
    'apr',
    'apss',
    'aqp',
    'arm',
    'arrc',
    'asa',
    'asc',
    'asid',
    'asla',
    'asp',
    'atc',
    'awb',
    'ba',
    'bca',
    'bcl',
    'bcss',
    'bds',
    'bem',
    'bls-i',
    'bn',
    'bpe',
    'bpi',
    'bpt',
    'bsc',
    'bt',
    'btcs',
    'bts',
    'cacts',
    'cae',
    'caha',
    'caia',
    'cams',
    'cap',
    'capa',
    'capm',
    'capp',
    'caps',
    'caro',
    'cas',
    'casp',
    'cb',
    'cbe',
    'cbm',
    'cbne',
    'cbnt',
    'cbp',
    'cbrte',
    'cbs',
    'cbsp',
    'cbt',
    'cbte',
    'cbv',
    'cca',
    'ccc',
    'ccca',
    'cccm',
    'cce',
    'cchp',
    'ccie',
    'ccim',
    'cciso',
    'ccm',
    'ccmt',
    'ccna',
    'ccnp',
    'ccp',
    'ccp-c',
    'ccpr',
    'ccs',
    'ccufc',
    'cd',
    'cdal',
    'cdfm',
    'cdmp',
    'cds',
    'cdt',
    'cea',
    'ceas',
    'cebs',
    'ceds',
    'ceh',
    'cela',
    'cem',
    'cep',
    'cera',
    'cet',
    'cfa',
    'cfc',
    'cfcc',
    'cfce',
    'cfcm',
    'cfe',
    'cfeds',
    'cfi',
    'cfm',
    'cfp',
    'cfps',
    'cfr',
    'cfre',
    'cga',
    'cgap',
    'cgb',
    'cgc',
    'cgfm',
    'cgfo',
    'cgm',
    'cgm',
    'cgma',
    'cgp',
    'cgr',
    'cgsp',
    'ch',
    'ch',
    'cha',
    'chba',
    'chdm',
    'che',
    'ches',
    'chfc',
    'chfc',
    'chi',
    'chmc',
    'chmm',
    'chp',
    'chpa',
    'chpe',
    'chpln',
    'chpse',
    'chrm',
    'chsc',
    'chse',
    'chse-a',
    'chsos',
    'chss',
    'cht',
    'cia',
    'cic',
    'cie',
    'cig',
    'cip',
    'cipm',
    'cips',
    'ciro',
    'cisa',
    'cism',
    'cissp',
    'cla',
    'clsd',
    'cltd',
    'clu',
    'cm',
    'cma',
    'cmas',
    'cmc',
    'cmfo',
    'cmg',
    'cmp',
    'cms',
    'cmsp',
    'cmt',
    'cna',
    'cnm',
    'cnp',
    'cp',
    'cp-c',
    'cpa',
    'cpacc',
    'cpbe',
    'cpcm',
    'cpcu',
    'cpe',
    'cpfa',
    'cpfo',
    'cpg',
    'cph',
    'cpht',
    'cpim',
    'cpl',
    'cplp',
    'cpm',
    'cpo',
    'cpp',
    'cppm',
    'cprc',
    'cpre',
    'cprp',
    'cpsc',
    'cpsi',
    'cpss',
    'cpt',
    'cpwa',
    'crde',
    'crisc',
    'crma',
    'crme',
    'crna',
    'cro',
    'crp',
    'crt',
    'crtt',
    'csa',
    'csbe',
    'csc',
    'cscp',
    'cscu',
    'csep',
    'csi',
    'csm',
    'csp',
    'cspo',
    'csre',
    'csrte',
    'csslp',
    'cssm',
    'cst',
    'cste',
    'ctbs',
    'ctfa',
    'cto',
    'ctp',
    'cts',
    'cua',
    'cusp',
    'cva',
    'cva[22]',
    'cvo',
    'cvp',
    'cvrs',
    'cwap',
    'cwb',
    'cwdp',
    'cwep',
    'cwna',
    'cwne',
    'cwp',
    'cwsp',
    'cxa',
    'cyds',
    'cysa',
    'dabfm',
    'dabvlm',
    'dacvim',
    'dbe',
    'dc',
    'dcb',
    'dcm',
    'dcmg',
    'dcvo',
    'dd',
    'dds',
    'ded',
    'dep',
    'dfc',
    'dfm',
    'diplac',
    'diplom',
    'djur',
    'dma',
    'dmd',
    'dmin',
    'dnp',
    'do',
    'dpm',
    'dpt',
    'drb',
    'drmp',
    'drph',
    'dsc',
    'dsm',
    'dso',
    'dss',
    'dtr',
    'dvep',
    'dvm',
    'ea',
    'ed',
    'edd',
    'ei',
    'eit',
    'els',
    'emd',
    'emt-b',
    'emt-i/85',
    'emt-i/99',
    'emt-p',
    'enp',
    'erd',
    # The load-bearing membership: the acronym test strips every
    # period, so this entry is the only thing matching the multi-dot
    # spelling, and removing it costs the family name ("John Smith
    # E.S.Q." -> family='E.S.Q.'). 'esq' is in SUFFIX_WORDS as well,
    # which against this set is inert -- "Esq" has no interior period,
    # so it matches here too -- but that is not a duplicate to clean
    # up: it is what still matches "Esq" if this entry ever goes.
    'esq',
    'evp',
    'faafp',
    'faan',
    'faap',
    'fac-c',
    'facc',
    'facd',
    'facem',
    'facep',
    'facha',
    'facofp',
    'facog',
    'facp',
    'facph',
    'facs',
    'faia',
    'faicp',
    'fala',
    'fashp',
    'fasid',
    'fasla',
    'fasma',
    'faspen',
    'fca',
    'fcas',
    'fcela',
    'fd',
    'fec',
    'fhames',
    'fic',
    'ficf',
    'fieee',
    'fmp',
    'fmva',
    'fnss',
    'fp&a',
    'fp-c',
    'fpc',
    'frm',
    'fsa',
    'fsdp',
    'fws',
    'gaee[14]',
    'gba',
    'gbe',
    'gc',
    'gcb',
    'gcb',
    'gchs',
    'gcie',
    'gcmg',
    'gcmg',
    'gcsi',
    'gcvo',
    'gcvo',
    'gisp',
    'git',
    'gm',
    'gmb',
    'gmr',
    'gphr',
    'gri',
    'grp',
    'gsmieee',
    'hccp',
    'hrs',
    'iaccp',
    'iaee',
    'iccm-d',
    'iccm-f',
    'idsm',
    'ifgict',
    'iom',
    'ipep',
    'ipm',
    'iso',
    'issp-csp',
    'issp-sa',
    'itil',
    'jd',
    'jp',
    'kbe',
    'kcb',
    'kchs/dchs',
    'kcie',
    'kcie',
    'kcmg',
    'kcsi',
    'kcsi',
    'kcvo',
    'kg',
    'khs/dhs',
    'kp',
    'kt',
    'lac',
    'lcmt',
    'lcpc',
    'lcsw',
    'lg',
    'litk',
    'litl',
    'litp',
    'llm',
    'lm',
    'lmsw',
    'lmt',
    'lp',
    'lpa',
    'lpc',
    'lpn',
    'lpss',
    'lsi',
    'lsit',
    'lt',
    'lvn',
    'lvo',
    'lvt',
    'ma',
    'maaa',
    'mai',
    'mba',
    'mbe',
    'mbs',
    'mc',
    'mcct',
    'mcdba',
    'mches',
    'mcm',
    'mcp',
    'mcpd',
    'mcsa',
    'mcsd',
    'mcse',
    'mct',
    'md',
    'mda',
    'mdb',
    'mdbb',
    'mdep',
    'mdhb',
    'mdiv',
    'mdl',
    'mem',
    'meng',
    'mfa',
    'micp',
    'mieee',
    'mirm',
    'mle',
    'mls',
    'mlse',
    'mlt',
    'mm',
    'mmad',
    'mmas',
    'mnaa',
    'mnae',
    'mp',
    'mpa',
    'mph',
    'mpse',
    'mra',
    'ms',
    'msa',
    'msc',
    'mscmsm',
    'msm',
    'mt',
    'mts',
    'mvo',
    'nbc-his',
    'nbcch',
    'nbcch-ps',
    'nbcdch',
    'nbcdch-ps',
    'nbcfch',
    'nbcfch-ps',
    'nbct',
    'ncarb',
    'nccp',
    'ncidq',
    'ncps',
    'ncso',
    'ncto',
    'nd',
    'ndtr',
    'nmd',
    'np',
    'np[18]',
    'nraemt',
    'nremr',
    'nremt',
    'nrp',
    'obe',
    'obi',
    'oca',
    'ocm',
    'ocp',
    'od',
    'om',
    'oscp',
    'ot',
    'pa-c',
    'pcc',
    'pci',
    'pe',
    'pfmp',
    'pg',
    'pgmp',
    'ph',
    'pharmd',
    'phc',
    'phd',
    'phr',
    'phrca',
    'pla',
    'pls',
    'pmc',
    'pmi-acp',
    'pmp',
    'pp',
    'pps',
    'prm',
    'psm',
    'psp',
    'psyd',
    'pt',
    'pta',
    'qam',
    'qc',
    'qcsw',
    'qfsm',
    'qgm',
    'qpm',
    'qsd',
    'qsp',
    'ra',
    'rai',
    'rba',
    'rci',
    'rcp',
    'rd',
    'rdcs',
    'rdh',
    'rdms',
    'rdn',
    'res',
    'rfp',
    'rhca',
    'rid',
    'rls',
    'rmsks',
    'rn',
    'rp',
    'rpa',
    'rph',
    'rpl',
    'rrc',
    'rrt',
    'rrt-accs',
    'rrt-nps',
    'rrt-sds',
    'rtrp',
    'rvm',
    'rvt',
    'sa',
    'same',
    'sasm',
    'sccp',
    'scmp',
    'se',
    'secb',
    'sfp',
    'sgm',
    'shrm-cp',
    'shrm-scp',
    'si',
    'siie',
    'smieee',
    'sphr',
    'sra',
    'sscp',
    'stb',
    'stmieee',
    'tbr-ct',
    'td',
    'thd',
    'thm',
    'ud',
    'usa',
    'usaf',
    'usar',
    'uscg',
    'usmc',
    'usn',
    'usnr',
    'uxc',
    'uxmc',
    'vc',
    'vc',
    'vcp',
    'vd',
    'vrd',
})
"""

Post-nominal acronyms. Titles, degrees and other things people stick after their name
that may or may not have periods between the letters. The parser removes periods
when matching against these pieces.

"""


# Guard the invariants the docstrings above promise, so a future edit that
# breaks them fails at import time instead of silently drifting until a test
# happens to catch it (same rationale as particles.py). Note `assert` is
# stripped under `python -O`; Lexicon re-checks the relationships at
# construction, which is what protects a caller's own vocabulary.
assert SUFFIX_ACRONYMS_AMBIGUOUS <= SUFFIX_ACRONYMS, \
    "SUFFIX_ACRONYMS_AMBIGUOUS must stay a subset of SUFFIX_ACRONYMS"
# NOT asserted: disjointness of SUFFIX_ACRONYMS and SUFFIX_WORDS.
# The two are matched with different normalization -- the word test strips
# only edge periods, the acronym test strips all of them -- and no
# SUFFIX_WORDS entry carries an interior period, so for a word in both
# sets the acronym branch fires wherever the word branch does (the assert
# just below keeps such a word out of the period-gated ambiguous subset).
# The single overlap, 'esq', is therefore inert as shipped rather than a
# second spelling: SUFFIX_ACRONYMS covers "E.S.Q." AND "Esq", and dropping
# 'esq' from SUFFIX_WORDS changes no parse. It stays because these sets
# are caller-editable -- it is what still matches "Esq" once 'esq' leaves
# SUFFIX_ACRONYMS -- and an inert overlap is not worth an assert that
# would reject a working config.
# DO assert that an ambiguous acronym is not also a plain suffix word:
# suffix_as_written ORs the two branches, so the word membership would
# bypass the period gate the ambiguous set exists to impose.
assert not (SUFFIX_ACRONYMS_AMBIGUOUS & SUFFIX_WORDS), \
    "an ambiguous acronym must not also be a suffix word (the word " \
    "branch bypasses its period gate): " \
    f"{sorted(SUFFIX_ACRONYMS_AMBIGUOUS & SUFFIX_WORDS)}"
# The peel splits its tail off as a TOKEN and suffix classification is
# what claims it downstream, so a tail that is not also a suffix word
# would split the name and then leave the piece sitting in it. The
# reverse direction is deliberately unguarded: a suffix word that is
# not a tail is the ordinary case, and an empty tail set is inert
# rather than wrong.
assert GLUED_HONORIFICS <= SUFFIX_WORDS, \
    "GLUED_HONORIFICS must stay a subset of SUFFIX_WORDS: " \
    f"{sorted(GLUED_HONORIFICS - SUFFIX_WORDS)}"
assert_normalized("suffix", SUFFIX_ACRONYMS | SUFFIX_WORDS)


# 1.x name, deprecated in 2.2 and removed in 3.0 (#293). The constant
# did not change module, so this aliases a name to one of this module's
# own globals: a module __getattr__ runs only once the body has finished
# and the module is in sys.modules, so the lookup resolves rather than
# recursing.
from nameparser.config._deprecated import alias_getattr  # noqa: E402

__getattr__, __dir__ = alias_getattr(__name__, {
    "SUFFIX_NOT_ACRONYMS": ("nameparser.config.suffixes", "SUFFIX_WORDS"),
})
