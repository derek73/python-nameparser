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


# See prefixes.py: keys are looked up in normalized form. Only the keys --
# the values are the exact-cased replacements, so they are cased on purpose.
assert all(k == k.strip().lower() for k in CAPITALIZATION_EXCEPTIONS), \
    "CAPITALIZATION_EXCEPTIONS keys must be stored lowercase and whitespace-free"
