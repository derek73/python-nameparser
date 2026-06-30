import re

# emoji regex from https://stackoverflow.com/questions/26568722/remove-unicode-emoji-using-re-in-python
re_emoji = re.compile('['  # lgtm[py/overly-large-range]
    '\U0001F300-\U0001F64F'
    '\U0001F680-\U0001F6FF'
    '\u2600-\u26FF\u2700-\u27BF]+',
    re.UNICODE)

EMPTY_REGEX = re.compile('')

REGEXES = set([
    ("spaces", re.compile(r"\s+", re.U)),
    ("word", re.compile(r"(\w|\.)+", re.U)),
    ("mac", re.compile(r'^(ma?c)(\w{2,})', re.I | re.U)),
    ("initial", re.compile(r'^(\w\.|[A-Z])?$', re.U)),
    ("quoted_word", re.compile(r'(?<!\w)\'([^\s]*?)\'(?!\w)', re.U)),
    ("double_quotes", re.compile(r'\"(.*?)\"', re.U)),
    ("parenthesis", re.compile(r'\((.*?)\)', re.U)),
    ("roman_numeral", re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I | re.U)),
    ("no_vowels",re.compile(r'^[^aeyiuo]+$', re.I | re.U)),
    ("period_not_at_end",re.compile(r'.*\..+$', re.I | re.U)),
    ("emoji",re_emoji),
    ("phd", re.compile(r'\s(ph\.?\s+d\.?)', re.I | re.U)),
    ("space_before_comma", re.compile(r'\s+,', re.U)),
    ("patronymic", re.compile(
        r'(ovich|ovna|evich|evna|ichna|ilyich|kuzmich|lukich|fomich|fokich)$',
        re.I | re.U,
    )),
    ("patronymic_cyrillic", re.compile(
        r'(ович|овна|евич|евна|ична|ильич|кузьмич|лукич|фомич|фокич)$',
        re.U,
    )),
])
"""
All regular expressions used by the parser are precompiled and stored in the config.
"""
