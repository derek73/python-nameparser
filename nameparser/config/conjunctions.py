from nameparser.config._invariants import assert_normalized

CONJUNCTIONS = {
    '&',
    'and',
    'et',
    'e',
    'of',
    'the',
    'und',
    'y',
    # #269: Cyrillic (ru/uk/bg) "and": и, і, та.
    'и',
    'і',
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
}
"""
Pieces that should join to their neighboring pieces, e.g. "and", "y" and "&".
"of" and "the" are also include to facilitate joining multiple titles,
e.g. "President of the United States".
"""


assert_normalized("CONJUNCTIONS", CONJUNCTIONS)
