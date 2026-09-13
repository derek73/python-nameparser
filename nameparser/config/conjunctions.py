from nameparser.config._invariants import assert_normalized

CONJUNCTIONS = frozenset({
    '&',
    'and',
    'et',
    'e',
    'of',
    'the',
    'und',
    'y',
    # #269: Cyrillic (ru/uk/bg) "and": и, і, та. Ukrainian writes і and
    # й for the same conjunction, alternating on the surrounding
    # vowel/consonant for euphony ("Олесь і Олена", "Марія й Петро"),
    # so real data carries both spellings and neither alone suffices.
    'и',
    'і',
    'й',
    'та',
    # #269: Greek "and": και.
    'και',
    # #269 follow-up: Arabic "and". Formal script attaches و to the
    # following word (وفاطمة), so a standalone و token appears only in
    # informal spacing -- common in real data. Single-character like
    # 'y'/'и': the single-letter carve-out (Google Code issue 11,
    # the "john e smith" bug) protects short names (joins
    # only with enough rootname pieces).
    'و',
})
"""
Pieces that should join to their neighboring pieces, e.g. "and", "y" and "&".
"of" and "the" are also include to facilitate joining multiple titles,
e.g. "President of the United States".
"""

CONJUNCTIONS_AMBIGUOUS = frozenset({
    # #383/#479: single letters that read as an INITIAL rather than a
    # connective when the input carries no case evidence -- a name
    # written wholly in one case, upper or lower alike. A letter
    # outside this set joins there, bare capital included.
    #
    # 'e' and not 'y', measured: a bare E initial is common (Edward,
    # Elizabeth) and an 'e' between two surnames is rare outside couple
    # listings; a bare Y initial is rare and 'y' between two surnames is
    # the commonest Hispanic compound and this library's oldest fixture
    # ('Velasquez y Garcia'). Cyrillic и/і/й follow y, not e: #267
    # blessed their joining and nothing here narrows it.
    #
    # 'i' (Catalan) is NOT here because it is not conjunction vocabulary
    # at all yet; it ships in this subset when #397 adds it, a bare I
    # initial being as common as a bare E.
    #
    # A caller edits the policy rather than a switch: remove 'e' to
    # restore joining for Portuguese data, add 'y' for a Dutch-style
    # "every single letter is an initial".
    'e',
})
"""
Single-letter entries of :data:`CONJUNCTIONS` that read as an initial,
not a connective, in a name written wholly in one case.
"""


assert_normalized("CONJUNCTIONS", CONJUNCTIONS)

# Guard the invariant the docstring promises, so a future edit that
# breaks it fails at import time (same rationale as suffixes.py). Note
# `assert` is stripped under `python -O`; Lexicon re-checks the
# relationship at construction, which is what protects a caller's own
# vocabulary.
assert CONJUNCTIONS_AMBIGUOUS <= CONJUNCTIONS, \
    "CONJUNCTIONS_AMBIGUOUS must stay a subset of CONJUNCTIONS"
assert all(len(w) == 1 and w.upper() != w.lower()
           for w in CONJUNCTIONS_AMBIGUOUS), \
    "CONJUNCTIONS_AMBIGUOUS holds CASED single letters; the fork only " \
    "reads a cased single-letter token, so a caseless letter (Arabic " \
    "و) or a multi-letter entry would be silently inert"
assert_normalized("CONJUNCTIONS_AMBIGUOUS", CONJUNCTIONS_AMBIGUOUS)
