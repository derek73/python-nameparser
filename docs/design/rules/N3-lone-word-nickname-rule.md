# N3 — the lone-word nickname rule

N3. Rationale: a person set down as a nickname plus one name word is
    being identified by surname.
    A name that is only a nickname and one name word reads that word
    as the family name; with two or more name words the ordinary
    positional reading applies.
      "'Smitty' Jones"            →  family="Jones"
      "'Smitty' John Jones"       →  given="John"  · boundary
    Accepted: the count does not set suffixes aside, so a nickname
    plus one name word plus a suffix reads the name word as given
    and leaves the family empty. A title counts against the count
    too, but H1 then reads the title-plus-one-word name that is
    left, so the family is named after all — unless the title is a
    given-name title, which keeps the word in `given` and leaves no
    family, exactly as it does anywhere else.
      "'Smitty' Jones Jr."        →  family=""
      "'Smitty' Dr. Jones"        →  family="Jones"
      "'Smitty' Sir John"         →  given="John"
    Accepted: a marker-led clause is a maiden clause and not a
    nickname one (M3), so this rule does not reach a name written
    that way, and the one name word keeps the reading the bare
    spelling gives it. Since #445 that reading is the family name
    all the same, M4 reaching both spellings from the other side.
    The two rules agree on THIS name and not in general: M4 counts
    name words alone, so where a suffix stands beside them it fires
    and this rule declines. The Accepted line above reads a bare
    nickname-plus-word-plus-suffix name as given with no family, and
    the same name carrying a maiden clause reads family instead.
      "Smith (née Jones)"         →  family="Smith"
    history: decisions.md#N3 · interacts: H1, M3, M4 · implemented: nameparser/_pipeline/_assign.py

