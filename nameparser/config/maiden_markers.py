from nameparser.config._invariants import assert_normalized

MAIDEN_MARKERS = {
    'née',
    'né',
    'nee',
    'geb',
    'geborene',
    'geboren',
    'roz',
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
}
"""
Marker words that introduce a birth surname, e.g. "Jane Smith née Jones"
(#274). French née/né/nee, German geb./geborene, Dutch geboren,
Czech/Slovak roz./rozená, Danish/Norwegian født (Nynorsk fødd), Swedish
född, Russian урожд./урождённая/урождённый (both ё and е spellings —
case normalization does not fold them, and running text routinely
writes е). Both grammatical genders are listed where #274 or review
attested them (née/né, урождённая/урождённый); Czech masculine rozený
awaits the same vetting. Entries are stored normalized: lowercase, no
periods.

Japanese 旧姓 is here rather than in locales.JA, on the rule that
admitted the Cyrillic entries: a native-script marker cannot collide
with a Latin-script name, and matching is whole-token, so it is safe
as a default. Neither character appears in any shipped surname, title,
suffix, conjunction, particle or bound-given vocabulary. locales.JA
is for what needs the my-data-is-Japanese declaration -- segmentation,
where a pure-Han string cannot say which language wrote it -- and this
needs none, since it can only ever match Han text.

Matching being whole-token, the marker has to BE a token, which for
Japanese means written with a space on each side. Both the bare
"山田花子 旧姓 佐藤" and -- since #329 -- the bracketed
"山田 花子（旧姓 佐藤）" under Policy(maiden_delimiters=...) give maiden
佐藤. What stays out of reach is the form Japanese more often writes,
a fullwidth colon after the marker: "山田（旧姓：佐藤）" still yields
maiden "旧姓：佐藤" with the marker and its colon attached. Not because
delimited content escapes classification -- classify tags a marker
wherever it is a token -- but because the colon glues marker and name
into ONE token, so there is nothing to drop. The wholly unspaced
"山田花子（旧姓佐藤）" glues the same way. Peeling a marker off the head
of a token is #317's job.

Consumed by the 2.0 parser's default lexicon. The 1.x parser does not
read this module.

Deliberately absent: Polish "z domu" (a two-token marker; pending the
2.0 pipeline's multi-token matching decision) and the Scandinavian
abbreviation "f." (collides with the initial "F." — only the full
participles are safe).
"""


assert_normalized("MAIDEN_MARKERS", MAIDEN_MARKERS)
