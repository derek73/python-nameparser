# H2 — the leading-abbreviation title

H2. Rationale: before a name, an abbreviation is almost always a
    title — "Rev.", "Ing.", "Mag." — and no vocabulary can list
    every profession's abbreviations in every language.
    An abbreviation opening the part of the name that carries the
    given name — the whole name, or the part after a family comma —
    reads as a title even when unlisted, provided it is an unbroken
    run of two or more letters ending in its one period; a bare
    initial does not, and neither does anything with interior
    periods, hyphens or digits. Where it fires, the shape outranks
    vocabulary: a period-marked opening word is a title even when
    the word is suffix vocabulary — except after a family comma,
    where a part that is nothing but suffix words is the credential
    run (C8) and the abbreviation opens nothing. An accented Latin,
    Greek or Cyrillic letter written as a base letter plus a
    combining mark (NFD) is the same letter as the composed one,
    for this shape and for the dotted and all-caps credential
    shapes C5, C6, S9 and S3 read (#652), so such a name parses the
    same in either encoding and the output keeps the one written.
      "Rev. John Smith"           →  title="Rev."
      "Xyz. John Smith"           →  title="Xyz."
      "Smith, Major. John"        →  title="Major."
      "Esq. Smith"                →  title="Esq."
      "J. Smith"                  →  given="J."  · boundary
      "J.R. Smith"                →  given="J.R."  · boundary
      "Dr. inž. Janez Novak"  →  title="Dr. inž."
    Accepted: the shape is only recognizable as an unbroken run of
    letters, so an abbreviation in a script whose letters carry
    combining vowel signs (Bengali, Devanagari) never reads as a
    title by shape — an unlisted abugida honorific stays a name
    word, and only vocabulary can recognize it — which is what #343
    and #344 supply for Bengali and Devanagari.
      "প্রকৌশলী. Sen"             →  given="প্রকৌশলী."
    Accepted: the shape reads a Latin convention, and a script with
    no initials has no period abbreviations either, so a period-
    marked opening word carrying a Han, kana or hangul character —
    as the script table classifies them, halfwidth katakana
    included since #594 — is a name word and never a
    title by shape (#323; decisions/cjk-full-stops) — the same
    veto that keeps 씨. from reading as an initial. The Latin
    reading is unchanged, and W3's example block carries the CJK
    reading this clause vetoes into. The veto reads the composed
    spelling, so hangul typed decomposed, as conjoining jamo the
    script table does not hold, is hangul to it too (#665); the
    second line below is typed that way.
      "Smith. John"               →  title="Smith."
      "김. 민준"                    →  title=""
    Accepted: before a family comma the shape does not fire: the
    titles there are the vocabulary's alone (H6), so an unlisted
    abbreviation opening that part stays in the family.
      "Xyz. Smith, John"          →  family="Xyz. Smith"
    Accepted: after a family comma a part that is nothing but suffix
    words is the credential run (C8), which the abbreviation does
    not open: the vocabulary decides, and "Esq." is the postnominal
    it is.
      "Smith, Esq."               →  suffix="Esq."
    Signal: a shape: an unlisted word of two or more letters ending in its one period, opening the given-name part
    history: decisions/H2 · interacts: C5, C6, C8, S3, P4, H5, H6, W3, W4, S9, T5 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py

