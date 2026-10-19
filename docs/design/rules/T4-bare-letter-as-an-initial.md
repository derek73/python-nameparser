# T4 — the bare letter as an initial

T4. Rationale: one letter standing for a name word is how an
    initial is written, and the writing marks it: by a period after
    the letter, or by a capital among mixed case, since nobody
    writes an initial in lower case beside capitals. A name written
    wholly in one case marks nothing, so its two spellings — all
    lower case and all capitals — are one name, and read alike.
    A one-letter word written with its period is an initial, in a
    script that writes initials, and so is a bare Latin capital; in
    a name written wholly in one case,
    which says nothing about any letter in it, a bare letter is an
    initial wherever its capital would be. So every rule that reads
    an initial differently from a name word reads the lower-case
    spelling as it reads the capitals: M4 leaves an initial its
    given-name reading, O5 reports no convention for one, P3's
    count passes over one, and S10 reads a numeral written as one
    as the capital numeral it is. A letter whose capital is no bare
    Latin capital — é, ж — is no initial in either spelling, and in
    a name of mixed case a bare lower-case letter is no initial. A single-letter connective among the name's own
    words is P3's question and not this one's: there the vocabulary
    decides, and the letter it does not mark reads as a connective
    in both spellings; a letter outside the name's own words — in
    a maiden clause, or past a marker the pass declines (M2) — is
    this rule's.
      "J NEE SMITH"               →  given="J"
      "j nee smith"               →  given="j"
      "j"                         →  ambiguities=()
      "jose j y lopez"            →  middle="j y"
      "smith, j y lopez"          →  given="j"
      "dr. née juan y lopez"      →  middle="juan y"
      "john j v"                  →  family="v"
      "Jose j y Lopez"            →  family="j y Lopez"  · boundary
      "é nee smith"               →  family="é"  · boundary
      "jose e lopez"              →  ambiguities=("conjunction-or-initial",)
      "jose y lopez"              →  middle="y"
    history: decisions/T4 · interacts: M4, O5, P3, P7, S10, R3 · implemented: nameparser/_pipeline/_classify.py
