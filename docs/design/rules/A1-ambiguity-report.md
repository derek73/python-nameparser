# A1 — the ambiguity report

A1. Rationale: a caller can only act on doubt that is reported.
    Parsing never fails on any input: where the text's structure or
    a word's reading is genuinely uncertain, the parse completes on
    the best reading and carries an ambiguity report naming the
    doubt. A report names the reading the parse took, so a report
    whose fork the rest of the parse then resolved to NEITHER branch
    is withdrawn rather than carried beside a reading it
    contradicts: a letter both a connective and an initial, read as
    the generation it also spells, is neither of the two the
    connective-or-initial fork offered, and only that fork's report
    goes — the generation's own stands. And a report that names the
    field its word was read into names the field the word holds in
    the result, whatever rule moved it after the report was made.
      "Van Johnson"               →  ambiguities=("particle-or-given",)
      "JOHN QUINCY SMITH I"       →  ambiguities=("suffix-or-name",)
      "Jane „JD Smith"            →  ambiguities=("unbalanced-delimiter",)
      "John Smith, MD, Bart"      →  ambiguities=("comma-structure",)
      "John Smith"                →  ambiguities=()  · boundary
    Accepted: the one exception to totality is a user-supplied
    segmenter's own error, which propagates — a user-code error is
    not a content error. (Needs the optional extra to demonstrate,
    so no example line.)
    history: decisions/A1 · interacts: H1, O1, O2, O3, P1, P3, P6, S2 · implemented: nameparser/_pipeline/_assemble.py, nameparser/_pipeline/_state.py

