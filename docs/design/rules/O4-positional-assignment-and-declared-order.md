# O4 — positional assignment and declared order

O4. Rationale: what no vocabulary claims can only be read by where
    it stands, under the order the caller declared.
    Words no vocabulary has claimed read by position. In the default
    given-first order the first name word is the given name, the
    last is the family name, and everything between is middle names.
    In a family-first order the first name word is the family; in
    family-first-given-last the given name comes from the end, the
    middles from between.
      "Mary Beth Smith"           →  middle="Beth"
      "Garcia Juan Carlos"  family-first  →  family="Garcia"
      "Nguyễn Thị Minh Khai"  family-first-given-last  →  given="Khai"
    no-boundary: this is the default reading every other rule carves
    exceptions from; its boundaries are the other rules.
    Signal: a position: where a word no vocabulary claimed stands, under the declared order
    implemented: nameparser/_pipeline/_assign.py

