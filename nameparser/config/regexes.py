import re

# emoji regex from https://stackoverflow.com/questions/26568722/remove-unicode-emoji-using-re-in-python
re_emoji = re.compile('['  # lgtm[py/overly-large-range]
    '\U0001F300-\U0001F64F'
    '\U0001F680-\U0001F6FF'
    '\u2600-\u26FF\u2700-\u27BF]+')

EMPTY_REGEX = re.compile('')

REGEXES = set([
    ("spaces", re.compile(r"\s+")),
    ("word", re.compile(r"(\w|\.)+")),
    ("mac", re.compile(r'^(ma?c)(\w{2,})', re.I)),
    ("initial", re.compile(r'^(\w\.|[A-Z])?$')),
    ("quoted_word", re.compile(r'(?<!\w)\'([^\s]*?)\'(?!\w)')),
    ("double_quotes", re.compile(r'\"(.*?)\"')),
    ("parenthesis", re.compile(r'\((.*?)\)')),
    ("roman_numeral", re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I)),
    ("no_vowels",re.compile(r'^[^aeyiuo]+$', re.I)),
    ("period_not_at_end",re.compile(r'.*\..+$', re.I)),
    ("emoji",re_emoji),
    ("phd", re.compile(r'\s(ph\.?\s+d\.?)', re.I)),
    ("space_before_comma", re.compile(r'\s+,')),
    ("east_slavic_patronymic", re.compile(
        r'(ovich|ovna|evich|evna|ichna|ilyich|kuzmich|lukich|fomich|fokich)$',
        re.I,
    )),
    ("east_slavic_patronymic_cyrillic", re.compile(
        r'(ович|овна|евич|евна|ична|ильич|кузьмич|лукич|фомич|фокич)$',
        re.I,
    )),
    ("turkic_patronymic_marker", re.compile(
        r"^(oglu|oğlu|ogly|ogli|o['’ʻ]g['’ʻ]li"
        r"|qizi|qızı|kizi|kyzy|gyzy|uly|uulu)$",
        re.I,
    )),
    ("turkic_patronymic_marker_cyrillic", re.compile(
        r'^(оглу|оглы|оғлу|ўғли|угли|кызы|гызы|қызы|қизи|улы|ұлы|уулу)$',
        re.I,
    )),
    ("period_abbreviation", re.compile(r'^[^\W\d_]{2,}\.$')),
])
"""
All regular expressions used by the parser are precompiled and stored in the config.
"""
