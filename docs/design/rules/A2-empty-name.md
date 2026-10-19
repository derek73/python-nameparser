# A2 — the empty name

A2. Rationale: an input with no name content names nobody, and
    saying so beats inventing fields from punctuation.
    A name with no name content parses to the empty name — every
    field empty, false as a boolean — while ambiguities born from
    its punctuation survive on the empty result.
      ".,"                        →  family=""
      "("                         →  ambiguities=("unbalanced-delimiter",)
      "John . Smith"              →  family="Smith"  · boundary
    Signal: a count: no name content, no letter or digit, in the input
    history: decisions/A2 · implemented: nameparser/_pipeline/_assemble.py

