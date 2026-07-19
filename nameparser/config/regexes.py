import re

# emoji ranges from https://stackoverflow.com/questions/26568722/remove-unicode-emoji-using-re-in-python
# Built from codepoint pairs rather than a literal character class:
# the compiled pattern is identical, but CodeQL's py/overly-large-range
# false-positives on literal astral ranges (surrogate decomposition).
_EMOJI_RANGES = ((0x1F300, 0x1F64F), (0x1F680, 0x1F6FF),
                 (0x2600, 0x26FF), (0x2700, 0x27BF))
re_emoji = re.compile(
    '[' + ''.join(f'{chr(lo)}-{chr(hi)}' for lo, hi in _EMOJI_RANGES) + ']+')

# Invisible bidirectional formatting characters: ALM, LRM, RLM, the
# embedding/override marks (LRE/RLE/PDF/LRO/RLO) and the isolates
# (LRI/RLI/FSI/PDI). Copy-pasted RTL names often carry these; they render
# as nothing but stick to name parts and break equality/lookups.
re_bidi = re.compile('[\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]+')

EMPTY_REGEX = re.compile('')

REGEXES = {
    "spaces": re.compile(r"\s+"),
    "word": re.compile(r"(\w|\.)+"),
    "mac": re.compile(r'^(ma?c)(\w{2,})', re.I),
    "initial": re.compile(r'^(\w\.|[A-Z])?$'),
    "quoted_word": re.compile(r'(?<!\w)\'([^\s]*?)\'(?!\w)'),
    "double_quotes": re.compile(r'\"(.*?)\"'),
    "parenthesis": re.compile(r'\((.*?)\)'),
    "roman_numeral": re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I),
    "period_not_at_end": re.compile(r'.*\..+$', re.I),
    "emoji": re_emoji,
    "bidi": re_bidi,
    "phd": re.compile(r'\s(ph\.?\s+d\.?)', re.I),
    "space_before_comma": re.compile(r'\s+,'),
    # ASCII comma plus its Arabic (U+060C) and fullwidth CJK (U+FF0C)
    # counterparts, used to split "Last, First" format and to strip a
    # trailing comma before parsing (#265).
    "commas": re.compile(r'[,،，]'),
    "east_slavic_patronymic": re.compile(
        r'(ovich|ovna|evich|evna|ichna|ilyich|kuzmich|lukich|fomich|fokich)$',
        re.I,
    ),
    "east_slavic_patronymic_cyrillic": re.compile(
        r'(ович|овна|евич|евна|ична|ильич|кузьмич|лукич|фомич|фокич)$',
        re.I,
    ),
    "turkic_patronymic_marker": re.compile(
        r"^(oglu|oğlu|ogly|ogli|o['’ʻ]g['’ʻ]li"
        r"|qizi|qızı|kizi|kyzy|gyzy|uly|uulu)$",
        re.I,
    ),
    "turkic_patronymic_marker_cyrillic": re.compile(
        r'^(оглу|оглы|оғлу|ўғли|угли|кызы|гызы|қызы|қизи|улы|ұлы|уулу)$',
        re.I,
    ),
    "period_abbreviation": re.compile(r'^[^\W\d_]{2,}\.$'),
}
"""
All regular expressions used by the parser are precompiled and stored in the config.
"""
