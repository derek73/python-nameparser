# P6 — the trailing orphan particle

P6. Rationale: a particle ending the name has nothing to link
    forward to, so it is not doing a particle's work there. What it
    is doing instead is decided by what the WRITING says, not by the
    word: where something has already named the family AND left the
    particle in a position that means nothing — after a family comma,
    or in the middle of a FAMILY_FIRST reading — it belongs to that
    family, which is how Dutch and Flemish names are listed
    ("Beethoven, Ludwig van", the tussenvoegsel trailing the given
    name but belonging to the surname). Where nothing has, it is
    read where it stands, and a particle CAN be a given name there:
    the never-given vocabulary supplies the reading position leaves
    open, and forbids nothing (parse("de") reports given "de", and
    so does every other word in that set).
    Where a family comma has already named the family, a particle
    ending the name attaches to that family name and is written
    before it — provided at least one given word remains, so that a
    name whose only given word is the particle keeps it (the
    words-to-spare test S2 applies to ambiguous suffixes). A
    post-nominal is written BEHIND the particle in this listing, so
    it does not end the name for this purpose: the run is found by
    looking past trailing words that hold no name — unless such a
    word is itself particle vocabulary, which makes it part of the
    run rather than something to look past. Where
    the word is BOTH a particle and suffix vocabulary, this
    attachment outranks the suffix reading (S2): a trailing
    abbreviation after a family comma is the tussenvoegsel far more
    often than the decoration it collides with. Three exceptions. The
    first is where the capitals speak: a word of the AMBIGUOUS
    credential class, written in capitals in a name written in more
    than one case, reads as the credential and this attachment stands
    down — unless a particle stands immediately in front of it, the
    two being one particle run by then, which this rule takes whole.
    The second is S2's company: such a word standing behind an
    unambiguous credential in one run of suffix words reads as the
    credential in any spelling and any case, reported as S2's
    credential fork. The third is a lone word of both the particle and
    the UNAMBIGUOUS suffix vocabulary standing INSIDE a run read as
    post-nominals — one in front of it and another behind, a
    credential or a generation, whatever made each one, and a title
    between it and the one in front transparent (H5): the
    tussenvoegsel stands right behind the given name, so a
    post-nominal between them says the word is not one. It does not
    end the name, and keeps the
    post-nominal reading in any case, reported as S2's credential
    fork. With nothing behind it, it ends the name and attaches, and
    two such words side by side are one particle run, which this rule
    takes whole. Every other spelling of such a word attaches as
    it did before, and the kind rule below gives it this rule's
    particle fork rather than S2's credential one. In a name written
    wholly in one case, with nothing in front of the word to speak
    for it, the two readings cannot be told apart and the particle
    keeps it, which is right about a Portuguese record and wrong
    about a credential; the report is how a caller finds the second.
      "Jong, Anke de"             →  family="de Jong"
      "Beethoven, Ludwig van"     →  family="van Beethoven"
      "Berg, Jan vd"              →  family="vd Berg"
      "Berg, Jan van der"         →  family="van der Berg"
      "Vega, Juan de la"          →  family_particles="de la"
      "Beethoven, Ludwig van"     →  family_base="Beethoven"
      "Beethoven, Ludwig van"     →  family_particles="van"
      "Nguyen, Van"               →  given="Van"  · boundary
      "Doe, John DO"              →  suffix="DO"  · boundary
      "Doe, John Do"              →  family="Do Doe"
      "SMITH, JOHN DO"            →  family="DO SMITH"
      "Doe, John van DO"          →  family="van DO Doe"
      "DOE, JANE PHD VD MA"       →  suffix="PHD VD MA"
      "doe, jane phd vd ma"       →  suffix="phd vd ma"
      "DOE, JANE PHD VD"          →  family="VD DOE"  · boundary
      "DOE, JANE MA VD PHD"       →  suffix="MA VD PHD"
    A particle an index form writes apart with its elision or its
    hyphen still on it is a particle like any other here, where the
    vocabulary lists that spelling — the elided "d'" and the Arabic
    article in its plain and assimilated spellings, "al-" among them
    — and of
    the never-given kind, since written apart the word is the article
    and nothing else. It joins with a space like every particle;
    written glued to the family ("d'Ivoi") it is one word and this
    rule never sees it.
      "Ivoi, Paul d'"             →  family="d' Ivoi"
      "Rashid, Harun al-"         →  family="al- Rashid"
      "Zaʿīm, Ḥusnī az-"          →  family="az- Zaʿīm"
    Without a comma, a declared family-first order has named the
    family in the same way and the attachment fires there too — but
    only where the run ENDS the name and stands in a MIDDLE — the one
    position that means nothing for it, middles being further given
    names, which a particle is not. Those two together name the
    order without asking it: the default order ends with the FAMILY
    and FAMILY_FIRST_GIVEN_LAST with the GIVEN name, so only
    FAMILY_FIRST can put a name's last word in a middle at all.
    Ending the name is not implied by the slot and has to be said. A
    draft that tested the slot alone fired on 52 default-order names,
    where a conjunction stops a particle's forward chain and leaves it
    standing in a middle, and on 366 FAMILY_FIRST_GIVEN_LAST middles
    with the given name still behind them.
    Nothing is asked about the WORD, and that is what lets one rule
    read both traditions: the same vocabulary that spells the Dutch
    tussenvoegsel spells the Vietnamese given name, and the declared
    order separates them where a comma cannot — one order, not both,
    as the Accepted clause below records.
    Nothing is re-laid-out either — under the order this can reach,
    the roles run family, given, middle, middle…, so dropping a
    trailing middle leaves every other piece where it was. That is a
    property of FAMILY_FIRST alone, and it is the second thing the
    two tests above secure. The family must hold a
    base of its own, since a family that is all particles is not a
    family written beside anything (R2).
      "Jong Anke de"  family-first  →  family="de Jong"
      "Jong Anke de"  family-first  →  given="Anke"
      "Ménil Christophe de"  family-first  →  family="de Ménil"
      "Ménil Christophe de"  family-first  →  given="Christophe"
      "Beethoven Ludwig van"  family-first  →  family="van Beethoven"
      "Ménil Christophe de"  family-first-given-last  →  given="de"
      "Berg Jan de Jr."  family-first  →  family="de Berg"
      "Berg Jan de Jr."  family-first  →  suffix="Jr."
      "van Berg Jan de"  family-first  →  family="van"  · boundary
      "Maria Luisa y de la Cruz"  →  family="la Cruz"  · boundary
      "de Anke van y"  family-first-given-last  →  middle="van"  · boundary
      "Ménil de"  family-first  →  given="de"  · boundary
      "Beethoven Ludwig van"  family-first  →  ambiguities=("particle-or-given",)
      "Jong Anke de"  family-first  →  ambiguities=()  · boundary
    Accepted: an ambiguous particle attaches on the same terms as a
    never-given one, so a Vietnamese name written in this listing
    loses its given name — but only in the UNACCENTED
    transliteration. Vân carries a diacritic and is not particle
    vocabulary, so the correctly spelled name never reaches this
    rule. It is the ASCII spelling that collides, and there the two
    traditions write the same string.
      "Nguyen, Thi Van"           →  family="Van Nguyen"
      "Nguyễn, Thị Vân"           →  family="Nguyễn"
    The fork is reported, in the kind naming the reading this
    attachment OVERRODE — what the run was read as before it fired,
    not what its words are. Where the run was read as a post-nominal,
    which is the S2 reading this rule outranks, the report is
    suffix-or-name. Otherwise, where the run holds an ambiguous
    particle, the reading overridden is that word as a name word, and
    the report is particle-or-given. Where the attachment overrode
    neither — a never-given particle read as a name word, which it
    could never have been — nothing was decided and nothing is
    reported.
      "Nguyen, Thi Van"           →  ambiguities=("particle-or-given",)
      "Berg, Jan vd"              →  ambiguities=("suffix-or-name",)
      "Jong, Piet de"             →  ambiguities=()  · boundary
    Accepted: the colliding spelling has a format that reads
    correctly, and it is ONE order, not both — FAMILY_FIRST_GIVEN_LAST,
    which is the order this name is written in. A line asserting what
    it does under FAMILY_FIRST stood here until #467 and was removed
    rather than updated: the name is not written in that format, so
    its reading there is wrong by construction and pins nothing worth
    keeping (#470).
      "Nguyen Thi Van"  family-first-given-last  →  family="Nguyen"
      "Nguyen Thi Van"  family-first-given-last  →  given="Van"
    Accepted: under the DEFAULT order a comma-less name's written
    shape is not settled — "Jong Anke de" may be a misformatted
    listing, and a bare "Jong de" may be a given name beside a
    particle — so nothing there names the family, the positional
    reading stands, and the same input reports family "de" here.
    That is the reading for a particle the UNAMBIGUOUS suffix
    vocabulary does not also claim, which is all but two of them.
    Where the word is both a particle and UNAMBIGUOUS suffix
    vocabulary — vd and mc — nothing has named the family, so the
    attachment above never fires and S2 takes the trailing word as
    a post-nominal, even though that leaves no family name at all:
    a bare "Donald mc" reports suffix "mc" with an empty family,
    and so does "Smith vd". The comma is the contrast, and it is
    where the precedence stated above acts, "Berg, Jan vd" reading
    family "vd Berg". `do` follows `de` rather than `mc`, sitting
    in the AMBIGUOUS acronym half, where S2's words-to-spare test
    leaves a two-word name its family.
      "Jong Anke de"              →  family="de"
    Accepted: the precedence over S2 is stated for the shape, so it
    sweeps in every word that is both particle and suffix
    vocabulary — today vd, do and mc. Only vd's reading was
    weighed; mc inherits it, which is the shape's cost and was
    decided rather than tracked — #454 closed by design 2026-09-07
    (decisions.md#suffix-acronym-collisions). `do` sits in the
    AMBIGUOUS acronym half and was already read as a name word
    there, so the precedence decides nothing for it — and because
    the report names the reading OVERRIDDEN, `do` reports
    particle-or-given while vd and mc report suffix-or-name. The
    same distinction decides a run of several words: a run read as
    name words reports on its ambiguous member if it has one and
    otherwise reports nothing, whatever its words could have been
    read as standing alone. Both are pinned in tests/v2/cases.py.
    Accepted: a bound given word ahead of the trailing particle takes
    it as its pair first (P5), so the attachment never sees it —
    unless the particle is of the unambiguous suffix vocabulary too
    (vd, mc), which the join declines and the attachment then takes.
      "Berg, abdul van"           →  given="abdul van"
      "Berg, abdul vd"            →  family="vd Berg"
    The comma site above and the no-comma family-first site earlier
    in this rule are checked against each other directly, as a pair,
    rather than only against their own examples: tests/v2/test_order_correspondence.py
    generates both writings and asserts they parse alike, plus a
    negative-control sweep pinning the disagreeing set the precedence
    bullet above names. A change that breaks one side of that pair
    should expect that test, not this file, to say so first.
    history: decisions.md#P6 · interacts: A1, C1, H5, P1, S2, P5, M2 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_post_rules.py

