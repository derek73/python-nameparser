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
}
"""
Pieces that should join to their neighboring pieces, e.g. "and", "y" and "&".
"of" and "the" are also include to facilitate joining multiple titles,
e.g. "President of the United States".
"""
