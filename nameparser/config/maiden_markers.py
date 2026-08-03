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

It reaches the SPACED form only ("山田花子 旧姓 佐藤" gives maiden
佐藤). Japanese more often writes the marker inside brackets, and
"山田（旧姓：佐藤）" under Policy(maiden_delimiters=...) still yields
maiden "旧姓：佐藤" with the marker and its colon attached: extract
claims delimited content whole, before classify has tagged anything
inside it, so group's marker-consuming rule never sees it. That
asymmetry is not Japanese -- "Jane Smith (née Jones)" keeps its marker
the same way -- and closing it is #329.

Consumed by the 2.0 parser's default lexicon. The 1.x parser does not
read this module.

Deliberately absent: Polish "z domu" (a two-token marker; pending the
2.0 pipeline's multi-token matching decision) and the Scandinavian
abbreviation "f." (collides with the initial "F." — only the full
participles are safe).
"""


assert_normalized("MAIDEN_MARKERS", MAIDEN_MARKERS)
