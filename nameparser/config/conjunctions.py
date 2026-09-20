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
    # #397: the Catalan/Polish surname link ("Carod i Rovira",
    # "Kowalski i Nowak"). Single-letter like 'y'/'и'/'e', and the one
    # entry that is ALSO generational vocabulary -- 'i' is the roman
    # numeral I, a bare entry of SUFFIX_WORDS -- so the carve-out
    # counts it as a name word for its own sake and it joins only
    # with a name word on each side (rules.md#P3).
    'i',
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
    # 'i' (Catalan/Polish) ships here beside 'e' for the same reason
    # (#397): a bare I initial is as common as a bare E, so a name
    # written wholly in one case reads the letter as an initial and
    # reports the fork rather than joining in silence.
    #
    # A caller edits the vocabulary rather than a switch: remove 'e' to
    # restore joining for Portuguese data, remove 'i' for Catalan or
    # Polish data, add 'y' for a Dutch-style "every single letter is an
    # initial".
    'e',
    'i',
})
"""
Single-letter entries of :data:`CONJUNCTIONS` that read as an initial,
not a connective, in a name written wholly in one case.
"""


assert_normalized("CONJUNCTIONS", CONJUNCTIONS)

# Guard the invariant the docstring promises, so a future edit that
# breaks it fails at import time (same rationale as suffixes.py).
# This holds the SHIPPED constant and nothing else, and two things
# follow. `assert` is stripped under `python -O`, so under -O even
# that much is gone. And unlike the other marker subsets, the pair is
# deliberately absent from Lexicon's subset checks, so a CALLER'S
# orphan is never rejected -- it is inert instead, the classify fork
# and its emitter both requiring the base entry before they read the
# marker (see decisions.md#P3, the 2026-09-13 entries).
assert CONJUNCTIONS_AMBIGUOUS <= CONJUNCTIONS, \
    "CONJUNCTIONS_AMBIGUOUS must stay a subset of CONJUNCTIONS"
assert all(len(w) == 1 and w.upper() != w.lower()
           for w in CONJUNCTIONS_AMBIGUOUS), \
    "CONJUNCTIONS_AMBIGUOUS holds CASED single letters; the fork only " \
    "reads a cased single-letter token, so a caseless letter (Arabic " \
    "و) or a multi-letter entry would be silently inert"
assert_normalized("CONJUNCTIONS_AMBIGUOUS", CONJUNCTIONS_AMBIGUOUS)
