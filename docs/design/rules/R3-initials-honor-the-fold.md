# R3 — initials honor the fold

R3. Rationale: initials abbreviate the person's name words; titles,
    suffixes, particles and nicknames are not name words.
    Initials take the first letter of each given, middle, and base
    family word; titles, suffixes, particles and nicknames
    contribute nothing — except the particles of a part whose every
    word is one, which are not acting as particles there (R2) and
    initial like any other name word. A connective contributes
    nothing where it is joining: a part holding another name word for
    it to join — the part's working particles set aside — is a part
    where the connective is doing a connective's work and is no name
    word of its own. A part holding nothing else is a part where it
    is joining nothing, and there it initials like any other name
    word, agreeing with the base.
    The first letter is the one the word's composed spelling begins
    with, written in the form the writer used: a letter written as a
    base letter followed by its combining accent initials whole, and
    so does a syllable written as its separate parts.
    The question is asked of the WHOLE PART, never of a word count. A
    part of two words where one is the connective is still a part
    where it joins — the base of "Jon Dough and" is "Dough and" and
    its initials are "J. D." — and a part of three is no different.
    One rule for every group. A connective written among given names
    is a connective there too and contributes nothing where it joins,
    so the group that was pinned-but-undocumented is now specified by
    the same sentence as the other two.
    Which words a group contributes is one question; the ORDER they
    contribute in is a second, and its answer is the field's. Each
    group initials in the order its field reads — written order,
    except folded family words, which initial before the rest of the
    family exactly as they render before it (R1). Stated here rather
    than left to R1, whose subject is every FIELD and which this view
    is not: what the view takes from the field is the ORDER it reads,
    and about order the two never disagree. Membership is the first
    question above and they can differ there — the family field of
    the first example line below is de la Vega, where the initials
    take its base — so this clause settles order and nothing else.
      "Dr. Juan Q. Xavier de la Vega III"  →  initials="J. Q. X. V."
      "Anh Do"                    →  initials="A. D."
      "Nguyen, Van Le"            →  initials="V. L. N."
      "Hassan, Mohamad Ahmad Ali"  middle_as_family  →  initials="M. A. A. H."
      "Sean O'Connor"             →  initials="S. O."  · boundary
      "émile zola"                →  initials="e\u0301. z."
      "マイケル ジャクソン"            →  initials="マ. シ\u3099."
    A family that is ALL particles therefore contributes its words
    rather than nothing: they are the base (R2), so they initial.
      "Juan van der"              →  initials="J. v. d."
      "Juan de y"                 →  initials="J. y."
      "John and Jane Smith"       →  initials="J. J. S."
      "Duke of Edinburgh"         →  initials="D. E."
      "Juan Velasquez y Garcia"   →  initials="J. V. G."
      "Jon Dough and"             →  initials="J. D."
    Accepted: this rule reads a part the parser read. A field set as
    raw text after the parse carries no reading, and this view is
    handed no vocabulary to supply one — it takes a format spec and
    two separators and nothing else — so every word of such a field
    initials, particles and conjunctions alike: a family set that way
    to "de la vega" gives "j. d. l. v." where parsing the same
    name gives "j. v.". Case repair IS handed a vocabulary, so it falls
    back for the one question a word can answer on its own, and R4
    says which. Revising the field through the parser classifies it
    and matches the parse in both of the parsed name's views. Stated
    without an example line because every line here names an input
    string, and this shape needs a field edited after the parse.
    The v1 facade's HumanName.initials() is a second view of this
    question and IS handed a vocabulary: it reads the parse's reading
    wherever a word is backed by a parsed token, and falls back
    wherever a word is not — a field set as raw text, or a name
    restored from a v1 pickle or copied through the same state hooks.
    The connective question falls back to the same helper case repair
    uses; the particle question was never asked of the parse in this
    view at all — `_is_particle` is a live
    vocabulary lookup for every word, backed or spliced alike — so a
    family spliced to "de la vega" initials "j. v." on this view
    against "j. d. l. v." on the parsed name's own. So the
    two views agree on WHICH WORDS initial in a parsed name; what
    still differs there is GROUPING, the facade initialing a joined
    run as one element, which is where the name "Ph. D., John" gives
    a run-together "J. P D." on this view against "J. P. D." on the
    other. Stated in prose and not as example lines because both
    shapes need a field edited after the parse, or a rendering the
    other view does not have. decisions/R3 carries what all of it
    costs and where it is pinned.
    Accepted: the given group's answer is a 1.4.0 parity break, and
    a second one in the other direction sits beside it. A connective
    among given names contributed an initial from 1.4.0 until this
    rule reached it, so "John and Jane Smith" gives "J. J. S." where
    every release through 2.3 gave "J. a. J. S." and 1.4.0 gave the
    run-together "J a J. S."; and a connective holding a part alone
    now contributes one, so "محمد و علي" gives "م. و. ع." on both
    views, which is 1.4.0's own answer restored. The rule is one
    sentence for all three groups, and taking it is what made the
    four candidate answers this group once had into one.
    Signal: none in the name: the parsed given, middle and base family words, and the connectives joining them
    history: decisions/R3 · interacts: O3, P3, P6, P8, R1, R2, R4 · implemented: nameparser/_render.py, nameparser/_facade.py, nameparser/_pipeline/_post_rules.py

