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

Consumed by the 2.0 parser's default lexicon. The 1.x parser does not
read this module.

Deliberately absent: Polish "z domu" (a two-token marker; pending the
2.0 pipeline's multi-token matching decision) and the Scandinavian
abbreviation "f." (collides with the initial "F." — only the full
participles are safe).
"""


# See prefixes.py: entries are looked up in normalized form, so a stray
# capital or trailing space makes one unreachable by direct membership
# test even though the parser's own ingest normalizes it away.
assert all(w == w.strip().lower() for w in MAIDEN_MARKERS), \
    "MAIDEN_MARKERS entries must be stored lowercase and whitespace-free"
