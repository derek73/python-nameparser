# N2 — same-character quotes and shared-character conventions

N2. Rationale: only a mark standing at word boundaries is quoting;
    anywhere else it is part of the word.
    A quote whose open and close are the same character opens only
    at a word start and closes only at a word end, so an apostrophe
    inside or at the end of a word is literal. Between conventions
    that share a character, position in the text decides: the
    leftmost valid opener wins — and a dangling-open report is
    suppressed where its character sits inside another pair's
    successful match, being literal content there rather than an
    imbalance (A1 depends on that filter).
      "Sean O'Connor"             →  family="O'Connor"
      "Hans „Erster“ und “Zweiter” Müller"  →  nickname="Erster Zweiter"
      "Mari' Aube'"               →  family="Aube'"  · boundary
    Signal: a position: where a quote character stands against the word boundaries
    history: decisions/N2 · implemented: nameparser/_pipeline/_extract.py

