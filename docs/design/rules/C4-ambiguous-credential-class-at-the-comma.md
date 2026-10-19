# C4 — the ambiguous credential class at the comma

C4. Rationale: two name words before the comma are read as a
    whole name, so for a word that is both a credential and a name
    the count decides before the writing does.
    For the ambiguous credential class — a bare acronym the
    vocabulary marks as also an ordinary name, and a word admitted
    to the class by shape, which S3 defines and bounds — the
    count before the comma is of NAME words rather than of words:
    two or more of them read the part after the comma as the
    credential run, whatever case the name is written in. The count
    goes FIRST and written case is asked only after it: where two
    name words stand before the comma the part after it is the
    credential run however that part is written, and only where the
    count leaves the word a name — one name word before the comma —
    is the case read, capitals in a mixed-case name making it the
    credential there too (S6). Paired initials are the exception to
    the count (C5), and an unlisted all-caps word is a word of this
    class here only where the name carries a case contrast (C6).
    The same count reads a part of two or
    more words as the credential run when every word of it is a
    suffix word or a word of this class, at least one of them of this
    class, and none of them a single-letter roman numeral, in any
    case: one letter is the shape a middle initial is written in,
    and S3 retires single-character matches for the same reason,
    while a multi-letter numeral or generational word stands in a
    run like any suffix word ('John Smith, III Ma'). A word's
    particle reading does not take it out of the run: a word of both
    the particle and the unambiguous suffix vocabulary is a suffix
    word there too ('John Smith, vd Ma'). Run membership asks what
    the word is, and S7's company asks whether it speaks for the word
    behind it, which a particle never does; the run S7 says such a
    word ends is the company's, not this count's. A word of both the
    title and the suffix vocabulary opening a part the count reads as
    a run counts as a suffix word there, the name before the comma
    being complete, except as the titles of paired initials (C5).
    Where every word
    of this class in the part is a LISTED word written in capitals in
    a mixed-case name, the writing has already made each of them the
    credential (S6), and the part reads as the credential run on that
    evidence rather than on the count; a word of the class by shape
    alone carries no such lean, so a part holding one is read by the
    count.
      "John Smith, MA"            →  suffix="MA"
      "John Smith, Ma"            →  suffix="Ma"
      "Smith, MA"                 →  suffix="MA"
      "Smith, Ma"                 →  given="Ma"
      "John Smith, Ed"            →  suffix="Ed"
      "Davis Royce, Ed"           →  suffix="Ed"
      "Royce, Ed"                 →  given="Ed"  · boundary
      "Smith Jr., MA"             →  suffix="Jr., MA"
      "Smith Jr., Ma"             →  given="Ma"  · boundary
      "John Smith, PhD MEng"      →  suffix="PhD MEng"
      "John Smith, Ed Ma"         →  suffix="Ed Ma"
      "Jane Doe, MS LAc"          →  suffix="MS LAc"
      "Smith, PhD MEng"           →  family="Smith"  · boundary
      "John Smith, PhD DO DO"     →  suffix="PhD DO DO"
      "John Smith, PhD vd DO"     →  suffix="PhD vd DO"
      "John Smith, vd Ma"         →  suffix="vd Ma"
      "JOHN SMITH, VD MA"         →  suffix="VD MA"
      "John Smith, X.Y.Z."        →  suffix="X.Y.Z."
      "John Smith, X.Y.Z."  unlisted_dotted_suffixes-off  →  given="X.Y.Z."
    Signal: a count: name words before the comma, for a word of the ambiguous class after it
    history: decisions/C4 · interacts: C1, C3, C5, C6, C11, S3, S4, S6, S7, S9 · implemented: nameparser/_pipeline/_comma.py
