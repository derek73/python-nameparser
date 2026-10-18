# S7 — the company of an unambiguous credential

S7. Rationale: post-nominals are written as a run, and an
    unambiguous degree in front of an ambiguous member says what the
    run is.
    Company is evidence that outranks both the count (S4) and the
    case (S6). A member of the ambiguous set standing BEHIND an
    unambiguous credential in one run of suffix words — members of
    the class between them passing the run on — reads as the
    credential whatever its writing and whatever the count, at every
    trailing slot S4 names: the degree in front says what the run
    is. Only a credential in FRONT speaks; one behind the member
    says nothing about it. A connective (P3), a particle (P2) — a
    word of both the particle and the suffix vocabulary heads the
    family name behind it — and a single-letter roman numeral, in
    any case — one letter, the shape a bare middle initial is
    written in, where a multi-letter one such as 'III' speaks —
    speak for nothing and end the run; so does any name word. A
    particle of this class standing behind a credential is still
    spoken for: the exclusion is of the word in front. A word of
    both the title and the suffix vocabulary standing in the given
    part's leading title run is a title there and speaks for
    nothing, and no credential behind it speaks for a word of this
    class in that part: the title reading makes the next word the
    given name, and from there the part reads as any given part
    does, the given part's own company included. A part holding no
    such word, or only words whose capitals decide them, reads as it
    did. Anywhere else such a word speaks like any suffix word.
    At the trailing slot of the given part this company outranks
    P6's attachment, as the capitals do. It does not reach across a
    maiden marker's clause (M2), whose name words stand between. A
    member the company decides reports the fork as a counted pick
    does, wherever it stands: at the trailing slots S4 names, and in
    a part after a family comma that the company leaves holding no
    name word, which reads wholly as the credential run. A member
    its own capitals already made the credential reports nothing
    new.
      "John Smith PhD MEng"       →  suffix="PhD MEng"
      "John Smith PhD Ed Ma"      →  suffix="PhD Ed Ma"
      "Wang Ma PhD"               →  family="Ma"  · boundary
      "Smith, PhD MEng"           →  suffix="PhD MEng"
      "Smith, Ms Ma"              →  given="Ma"  · boundary
      "Smith, PhD Ma"             →  suffix="PhD Ma"
      "Smith, PhD Ma"             →  ambiguities=("suffix-or-name",)
      "Smith, MD PhD Ma"          →  given="PhD"  · boundary
      "Doe, Jane PhD MEng"        →  suffix="PhD MEng"
      "doe, jane v phd do"        →  suffix="v phd do"
    Accepted: a name-leaning member with nothing in front of it to
    speak for it ends the name, words to spare or not, and whatever
    stands in front of it is name text. Where a credential does
    stand in front, the company above decides instead, except in
    one shape that keeps it out of reach and reads the member as the
    name: a credential written split across two words with no comma
    after the name. That reading is older than the company clause,
    so it is witnessed by tests/v2/cases.py's
    a_split_degree_in_front_is_out_of_the_walk rather than by a line
    here, which would promise a reading this clause did not make.
    A title standing between the credential and the member, and a
    member a particle chain (P2) had taken, were two more such shapes
    until the credential's run (S8) took both in: the rows
    a_title_between_degree_and_member_keeps_it_a_name and
    a_member_the_particle_chain_took_is_out_of_reach keep their ids
    and now pin the run.
      "Jack Wei Ma"               →  family="Ma"
      "Jack Wei Ma"               →  ambiguities=("suffix-or-name",)
      "abdul Smith Jr Ma"         →  suffix="Jr Ma"
    history: decisions/S7 · interacts: C1, M2, P2, P3, P6, S4, S5, S6, S8 · implemented: nameparser/_pipeline/_comma.py, nameparser/_pipeline/_pieces.py
