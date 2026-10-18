# T1 — separators, not joiners

T1. Rationale: a character that carries no name content (emoji, an
    invisible directionality control) stands between words, not
    inside them.
    A name splits at whitespace and — unless the caller opts to
    keep them — at ignorable characters: an ignorable character
    separates its neighbors and never joins them.
      "John😀Smith"                →  family="Smith"
      "John😀Smith"  keep-emoji    →  given="John😀Smith"  · boundary
    history: decisions.md#T1 · implemented: nameparser/_pipeline/_tokenize.py

