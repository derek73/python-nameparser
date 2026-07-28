from nameparser.config._invariants import assert_normalized

CAPITALIZATION_EXCEPTIONS = {
    'ii': 'II',
    'iii': 'III',
    'iv': 'IV',
    'md': 'M.D.',
    'phd': 'Ph.D.',
}
"""
Any pieces that are not capitalized by capitalizing the first letter.
"""


# Keys only -- the values are the exact-cased replacements, cased on purpose.
assert_normalized("CAPITALIZATION_EXCEPTIONS", CAPITALIZATION_EXCEPTIONS)
