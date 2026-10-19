# C1 — the suffix-comma decision

C1. Rationale: a credential run after the comma means the name is in
    natural order with suffixes appended; anything else after the
    comma means the listing form.
    With a comma present, the name reads as trailing suffixes when
    the part after the first comma is entirely suffix words and more
    than one word precedes the comma; otherwise it reads as the
    listing form, the part before the comma being the family name,
    less a title run opening it (H6), unless the part after it fixes
    no family boundary (C8). Only
    the part after the first comma decides, but for a suffix word
    ending a whole name before it (C12). The rules after this one
    say how the decision reads what it reads: how the words before
    the comma are counted (C3); the ambiguous credential class,
    counted by name words (C4), with paired initials (C5) and an
    unlisted all-caps word (C6) read there by rules of their own; a
    part read as postnominal, read before any join (C7); the listing
    form's part after the comma, still read for what it is (C8); a
    one-character suffix word inside a comma part (C9); a declared
    delimiter, which parts a trailing suffix part as a comma would
    (C10); what the decision reports (C11); and a suffix word ending
    the name before the comma (C12).
    By default a recognized suffix word counts
    even written like an initial ("V."), while strict mode vetoes
    a word read as an initial — in a name written in one case a
    bare lower-case letter as well, as its capital is (T4).
      "Smith, John"               →  family="Smith"
      "سلمان، محمد"               →  family="سلمان"
      "田中、太郎"                 →  family=""
      "John Smith, PhD"           →  suffix="PhD"
      "John Smith, V."            →  suffix="V."
      "John Smith, V."  strict-comma-suffixes  →  family="John Smith"
      "john smith, v"  strict-comma-suffixes  →  family="john smith"
      "Smith, PhD"                →  family="Smith"  · boundary
      "John Smith, Jones"         →  family="John Smith"
    Accepted: the vocabulary question above — is the part after the
    comma nothing but suffix words — is asked a second time, without
    the word-count condition, to decide whether a glued East Asian
    honorific standing before a family comma comes off. That
    composition is tolerated input rather than contract — a comma
    between a family name and a given name is no part of CJK writing
    — so the precedence is stated at W3, with its examples, and not
    here. It is also the one consequence of this question Latin
    script cannot witness, nothing there being glued to the end of a
    name — which is why this clause carries no example of its own.
    history: decisions/C1 · interacts: C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, H6, T4, W3 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_comma.py
