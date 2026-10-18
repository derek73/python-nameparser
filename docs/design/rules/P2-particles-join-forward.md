# P2 — particles join forward

P2. Rationale: a particle is written as part of the surname it
    precedes, and a title stands outside the name entirely.
    A particle joins the words after it into one name part, the
    join running until the next particle starts a group of its own,
    a trailing suffix begins — the trailing run S2 reads, once,
    before the chain is made and counting the chain's own run as the
    one name word it will be, so the chain cannot change what it
    counts: a trailing roman numeral, or a
    bare acronym with words to spare, ends the chain as a suffix word
    does, and so does a bare ambiguous acronym written in capitals in
    a mixed-case name, which needs no words to spare; the same
    acronym written Title-case in a mixed-case name ends nothing and
    joins the chain as any name word does, words to spare or not,
    and the fork the chain called is reported there exactly as it is
    where no particle stands (S4) —
    a maiden
    marker takes the
    words after it (M2), or the name ends. The final group reads as
    the family name;
    earlier groups read by position. The chain begins wherever the
    name begins, and a preceding title does not move that point.
    Where P1's fold has claimed the opening, the fold decides the
    family instead — and may take only PART of the final group,
    since it counts name words and the group is one part.
    In the part before a family comma, which the comma named the
    family, a particle that is also suffix vocabulary heads the name
    word behind it, whatever case the name is written in, and is not
    read as a suffix standing between two family words; with a suffix
    word or nothing behind it, it reads as the suffix it is there. A
    lone letter behind it reads as it does in the same part without
    the particle: a capital is a name word ('SMITH VD V, JOHN' as
    'SMITH V, JOHN'), a lowercase letter the numeral ('smith vd v,
    john' as 'smith v, john').
      "John van der Berg"         →  family="van der Berg"
      "John van der Berg Smith"   →  family="van der Berg Smith"
      "Vincent van Gogh van Beethoven"  →  middle="van Gogh"
      "Dr. John van der Berg"     →  family="van der Berg"
      "Juan de"                   →  family="de"  · boundary
      "de la Cruz Juan Carlos"  family-first  →  family="de la Cruz"
      "John van der Berg PhD"     →  family="van der Berg"
      "John van der Berg V"       →  family="van der Berg"
      "John van der Berg V"       →  suffix="V"
      "John van der Berg Ma"      →  family="van der Berg Ma"
      "John van der Berg Ma"      →  ambiguities=("suffix-or-name",)
      "john van der berg ma"      →  suffix="ma"
      "John van der J. V"         →  family="van der J. V"  · boundary
      "Freiherr von Berg MA"      →  family="von Berg"
      "Freiherr von Berg MA"      →  suffix="MA"
      "Freiherr von Richthofen V" →  suffix="V"  · boundary
      "SMITH VD MA, JOHN"         →  family="SMITH VD MA"
      "SMITH VD, JOHN"            →  suffix="VD"  · boundary
      "John van der Berg née Jones"  →  family="van der Berg"
    Accepted: a particle of the unambiguous suffix vocabulary too
    (vd, mc) is a suffix piece to the peel, so where it opens the
    trailing run the chain stops before it as before any suffix
    word, and the peel takes it; where it continues a prefix run,
    the run takes it as a particle, as P6 reads it after a comma —
    and there the chain reports nothing, the particle reading being
    P6's fork rather than S4's.
    The same carve-out covers `do`, the one word that is both a
    particle and an AMBIGUOUS credential acronym: where a particle
    run takes it, the word is the run's and the chain reports
    nothing, whatever case it is written in — so `Anh van Do` is
    silent where `Anh Do`, with no particle standing, reports.
    A word that is both belongs to the particle run and to P6's
    fork, not to S4's.
      "John Smith Mc V"           →  suffix="Mc V"
      "John van Mc"               →  family="van Mc"
      "anh van do"                →  family="van do"  · boundary
      "anh van do"                →  ambiguities=()  · boundary
      "Anh van Do"                →  family="van Do"  · boundary
      "Anh van Do"                →  ambiguities=()  · boundary
    Accepted: a caller wanting the combined double-surname reading
    (#132's ask) has it as the surnames view rather than the
    family field.
      "Vincent van Gogh van Beethoven"  →  surnames="van Gogh van Beethoven"
    history: decisions/P2 · interacts: P1, P4, H5, M2, S2, C2, S4 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_post_rules.py

