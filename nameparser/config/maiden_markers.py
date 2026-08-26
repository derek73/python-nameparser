from nameparser.config._invariants import assert_normalized

MAIDEN_MARKERS = frozenset({
    'née',
    'né',
    'nee',
    'geb',
    'geborene',
    'geboren',
    'rozená',
    'født',
    'fødd',
    'född',
    'урожд',
    'урождённая',
    'урожденная',
    'урождённый',
    'урожденный',
    '旧姓',
})
"""
Marker words that introduce a birth surname, e.g. "Jane Smith née Jones"
(#274). French née/né/nee, German geb./geborene, Dutch geboren,
Czech/Slovak rozená, Danish/Norwegian født (Nynorsk fødd), Swedish
född, Russian урожд./урождённая/урождённый (both ё and е spellings —
case normalization does not fold them, and running text routinely
writes е). Both grammatical genders are listed where #274 or review
attested them (née/né, урождённая/урождённый); Czech masculine rozený
awaits the same vetting, and would be vetted on its own merits rather
than following the feminine form in — the abbreviation roz. shared by
both genders is deliberately absent, below. Entries are stored
normalized: lowercase, no periods.

Japanese 旧姓 is here rather than in locales.JA, on the rule that
admitted the Cyrillic entries: a native-script marker cannot collide
with a Latin-script name, and matching is whole-token, so it is safe
as a default. Neither character appears in any shipped surname, title,
suffix, conjunction, particle or bound-given vocabulary. locales.JA
is for what needs the my-data-is-Japanese declaration -- segmentation,
where a pure-Han string cannot say which language wrote it -- and this
needs none, since it can only ever match Han text.

Matching being whole-token, the marker has to BE a token -- which for
Japanese means something has to divide it from the name it marks. A
space does, and so does a delimiter: extract masks the whole bracketed
region, delimiter characters included, before tokenize runs, so a
bracket bounds a token exactly as a space does and "山田（旧姓 佐藤）"
needs no space in front of 旧姓 at all. The bare "山田花子 旧姓 佐藤"
and the bracketed "山田 花子（旧姓 佐藤）" alike give maiden 佐藤, and
since #335 the bracketed form needs no configuration to do it: the
fullwidth pair is a NICKNAME delimiter by default, and rules.md#M3
reads a clause that opens with a marker word AND carries a word after
it as the maiden name, whichever bucket its pair sits in. The second
word is part of the condition, not a detail of it -- a lone "（旧姓）"
is a word in brackets and stays a nickname. #329, which drops the marker from inside the
clause, is what makes the value 佐藤 rather than "旧姓 佐藤". Declaring
the pair in Policy(maiden_delimiters=...) reaches the same reading by
M1's path. What divides nothing is the fullwidth colon that the form
Japanese more often writes puts after the marker: "山田（旧姓：佐藤）"
under Policy(maiden_delimiters=...) still yields maiden "旧姓：佐藤"
with the marker and its colon attached. Not because delimited content
escapes classification -- classify tags a marker wherever it is a
token -- but because ： is no separator tokenize knows, so marker and
name arrive as ONE token and there is nothing to drop. M3 does not
reach that form either, and by its own test rather than by tokenize's:
it splits the clause on WHITESPACE, and "旧姓：佐藤" is one whitespace
word, so there is no marker word for the clause to open with and by
default it stays a nickname. The two tests agree here and are
deliberately not the same test -- see decisions.md#M3. The wholly
unspaced "山田花子（旧姓佐藤）" reads as one token for the same reason.
Peeling a marker off the head of a token is #317's job.

Consumed by the 2.0 parser's default lexicon. The 1.x parser does not
read this module.

Deliberately absent: Polish "z domu" (a two-token marker; pending the
2.0 pipeline's multi-token matching decision), the Scandinavian
abbreviation "f." (collides with the initial "F." — only the full
participles are safe), and the Czech/Slovak abbreviation "roz."
(shipped through 2.1 and removed in 2.2). Roz is an ordinary English
diminutive of Rosalind, and matching is whole-token, case-folded and
period-insensitive, so "Roz", "roz" and "roz." are one string to this
set: with it shipped, "Rosalind Roz Smith" read maiden "Smith" and NO
family name at all. The collision is in the position the claim acts
on, which is the test decisions.md#vocabulary-collisions states, and
this set has no ambiguous subset to express a partial answer in — see
decisions.md's Excluded (MAIDEN_MARKERS) block. The full participle
rozená stays, being unambiguous; a caller who needs the abbreviation
adds it to their own Lexicon.
"""


assert_normalized("MAIDEN_MARKERS", MAIDEN_MARKERS)
