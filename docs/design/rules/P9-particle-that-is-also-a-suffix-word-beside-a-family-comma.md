# P9 — a particle that is also a suffix word, beside a family comma

P9. Rationale: a word of both the particle and the suffix vocabulary
    is a surname particle where it stands among name words and a
    post-nominal where it stands among post-nominals, and both
    readings are written in every case; beside a family comma, which
    has already named the family, its neighbors tell which it is and
    the case it is written in does not.
    In the part before a family comma, which the comma named the
    family, a particle that is also suffix vocabulary heads the name
    word behind it, whatever case the name is written in, and is not
    read as a suffix standing between two family words; with a suffix
    word or nothing behind it, it reads as the suffix it is there. A
    lone letter behind it reads as it does in the same part without
    the particle: a capital is a name word ('SMITH VD V, JOHN' as
    'SMITH V, JOHN'), a lowercase letter in a name of mixed case the
    numeral ('Smith vd v, John' as 'Smith v, John'), and a name
    written in one case reads as its capitals (T4).
    In the part after a family comma, where P6 attaches a particle
    ending the name to the family, a lone word of both the particle and
    the UNAMBIGUOUS suffix vocabulary standing INSIDE a run read as
    post-nominals — one in front of it and another behind, a
    credential or a generation, whatever made each one, and a title
    between it and the one in front transparent (H5) — is not the
    tussenvoegsel: that stands right behind the given name, so a
    post-nominal between them says the word is not one. It does not
    end the name, and keeps the post-nominal reading in any case,
    reported as S4's credential fork. With nothing behind it, it
    ends the name and P6 attaches it, and two such words side by
    side are one particle run, which P6 takes whole.
      "SMITH VD MA, JOHN"         →  family="SMITH VD MA"
      "SMITH VD, JOHN"            →  suffix="VD"  · boundary
      "DOE, JANE PHD VD MA"       →  suffix="PHD VD MA"
      "doe, jane phd vd ma"       →  suffix="phd vd ma"
      "DOE, JANE PHD VD"          →  family="VD DOE"  · boundary
      "DOE, JANE MA VD PHD"       →  suffix="MA VD PHD"
    Signal: a neighbor: the words beside a particle that is also suffix vocabulary, on either side of a family comma
    history: decisions/P9 · interacts: P2, P6, S2, S4, S6, S7, H5, T4 · implemented: nameparser/_pipeline/_assign.py
