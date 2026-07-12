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
född, Russian урожд./урождённая (both ё and е spellings —
``str.casefold()`` does not fold them, and running text routinely
writes е). Entries are stored normalized: lowercase, no periods.

Consumed by the 2.0 parser's default lexicon. The 1.x parser does not
read this module.

Deliberately absent: Polish "z domu" (a two-token marker; pending the
2.0 pipeline's multi-token matching decision) and the Scandinavian
abbreviation "f." (collides with the initial "F." — only the full
participles are safe).
"""
