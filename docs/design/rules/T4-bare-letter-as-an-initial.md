# T4 — the bare letter as an initial

T4. Rationale: one letter standing for a name word is how an
    initial is written, and the writing marks it: by a period after
    the letter, or by a capital among mixed case, since nobody
    writes an initial in lower case beside capitals. A name written
    wholly in one case marks nothing, so its two spellings — all
    lower case and all capitals — are one name, and read alike.
    A one-letter word written with its period is an initial, in a
    script that writes initials, and so is a bare unaccented Latin
    capital, A to Z; in a name written wholly in one case,
    which says nothing about any letter in it, a bare letter is an
    initial wherever its capital would be. So every rule that reads
    an initial differently from a name word reads the lower-case
    spelling as it reads the capitals: M4 leaves an initial its
    given-name reading, O5 reports no convention for one, P3's
    count passes over one, S10 reads a numeral written as one
    as the capital numeral it is, and a suffix test that vetoes an
    initial vetoes it — C1's strict mode, and the scan-back of W2's
    peel. A letter whose capital is not one
    of those — é, ж — is no initial in either spelling, and in a
    name of mixed case a bare lower-case letter is no initial. As
    P3 asks it, the case question is asked of the name's own words,
    so a clause beside the name changes nothing about the name's own
    letters: a lone letter before a maiden name in capitals is still
    a name written in one case. A single-letter connective among the name's own
    words is P3's question and not this one's: there the vocabulary
    decides, and the letter it does not mark reads as a connective
    in both spellings; a letter outside the name's own words — in
    a maiden clause, or past a marker the pass declines (M2) — is
    this rule's, and asks the case of the whole name, the clause
    included, since the own words' case says nothing of how the
    clause beside them was written.
      "J NEE SMITH"               →  given="J"
      "j nee smith"               →  given="j"
      "j"                         →  ambiguities=()
      "jose j y lopez"            →  middle="j y"
      "smith, j y lopez"          →  given="j"
      "dr. née juan y lopez"      →  middle="juan y"
      "john j v"                  →  family="v"
      "Jose j y Lopez"            →  family="j y Lopez"  · boundary
      "é nee smith"               →  family="é"  · boundary
      "j nee Smith"               →  given="j"
      "DR. NÉE JUAN y LOPEZ"      →  family="JUAN y LOPEZ"  · boundary
      "jose e lopez"              →  ambiguities=("conjunction-or-initial",)
      "jose y lopez"              →  middle="y"
    Accepted: the numeral ending a maiden clause is M2's question,
    and the take asks the letter in front of it by its own writing
    alone, so a clause written in lower case can end otherwise than
    its capitals. Nobody writes an initial straight after a maiden
    marker, so the shape this reaches is not one names take.
      "john smith nee x x"        →  suffix="x"
      "JOHN SMITH NEE X X"        →  maiden="X X"
    Signal: a shape: a one-letter word's period + a case contrast: a bare letter's case against the name's own words
    history: decisions/T4 · interacts: M2, M4, O5, P2, P3, P7, S10, R3, R4, C1, W2 · implemented: nameparser/_pipeline/_classify.py, nameparser/_pipeline/_vocab.py
