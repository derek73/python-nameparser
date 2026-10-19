# C11 — what the comma decision reports

C11. Rationale: the comma's reading is a call the parse made, and
    a reader who could have taken the words the other way is told
    that it was made.
    A decision either way at the comma C1 reads
    is reported; for a run of words the decision is the flip to the
    credential run, reported once over the whole part. A flip in which
    no listed word of the ambiguous credential class (C4) takes part
    is the exception and is
    made in silence, since only paired initials among such words are
    ever taken for a name, and the flip reaches them only where
    something else in the part has said otherwise — unless what said
    so is nothing but other paired initials: each of those is a word
    a reader takes for a name, and that flip is reported. Paired
    initials the comma keeps as the given name (C5) report where they
    open the part; behind a title they do not, the comma's report
    reaching only the first word after it ('Smith, Ms G.J.'). A run the
    count leaves in the listing form reports as S7 reads the words
    in it: a word of this class read as the credential because a
    credential in front speaks for it reports, and one its own
    capitals made the credential does not unless it opens the part,
    where it is the first word after the comma and reports as that
    word always does ('Doe, MA PhD', 'John Smith, MA MA'). So a run
    whose every such word is written in capitals reads whole in
    silence only behind another credential ('John Smith, PhD MA',
    'Smith, PhD MA'), as does a part read as titles before a lone
    given name ('Smith, Ms MD Ma'). It is one
    of TWO places the comma's own decision is reported, the other being the word trailing the given part after
    it (S5), which is a second decision about a second word and never
    the same fork twice; an attachment decided after a family comma
    (P6) reports on its own. C2's comma-structure flag reports what the
    parse could not recognize, not a fork it called.
      "Doe, MA PhD"               →  ambiguities=("suffix-or-name",)
      "John Smith, PhD Jones"     →  ambiguities=("suffix-or-name",)
      "John Smith, PhD DO DO"     →  ambiguities=()  · boundary
      "JOHN SMITH, VD MA"         →  ambiguities=("suffix-or-name",)
      "John Smith, Jr vd"         →  ambiguities=()
      "John Smith, Jr do"         →  ambiguities=("suffix-or-name",)
      "John Smith, X.Y.Z."        →  ambiguities=()
      "John Smith, XYZ"           →  ambiguities=("suffix-or-name",)
      "John Smith, A.B."          →  ambiguities=("suffix-or-name",)
      "De La Cruz, M.J. K.L."     →  ambiguities=("suffix-or-name", "suffix-or-name")
    history: decisions/C11 · interacts: A1, C1, C2, C4, C5, P6, S5, S6, S7 · implemented: nameparser/_pipeline/_comma.py
