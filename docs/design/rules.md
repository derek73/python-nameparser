# Parsing rules

This document is NORMATIVE, not descriptive: the rules state how names are written and what should happen when they are parsed, grounded in how people understand names — not in what the parser currently does. The parser implements these rules. Where it does not yet, the gap is a tracked deviation (`deviates:` marker below), not a counterexample. Statements are implementation-free: no stage names, no function names, no regexes.

Authority, scoped: `tests/v2/cases.py` pins CURRENT behavior; this document states INTENDED behavior. A mismatch between them must be classified, never defaulted: either the rule is wrong (fix it here) or the parser is wrong (the example takes a `deviates:` marker and an issue). Where this document is silent, the behavior is pinned-but-undocumented — an extraction gap to close, not a specification, and not license to change the behavior.

Rule IDs are stable forever: never renumbered, never reused. A retired rule keeps its ID with a one-line tombstone pointing at decisions.md. Cross-references use the anchor form `decisions.md#P2` / `mechanisms.md#SPANS`; a bare ID is never a citation. The `interacts:` field on a pointer line is advisory — the citation-integrity test checks the ID exists, not that the interaction is real. `implemented:` and `tracked:` are not advisory: every rule carries exactly one. `implemented:` names the modules honoring the rule, checked against the modules that cite it; `tracked:` names the issues that would ship a rule nothing implements yet, so a wholly-aspirational rule cannot sit here untracked, and a shipped rule cannot keep a stale tracking pointer.

Every example line is EXECUTABLE. The grammar (its executable definition is `tests/v2/rules_doc.py`; `tests/v2/test_rules_doc.py` runs every line):

    "INPUT" [annotation] →  field="value"  [· boundary]
                            [deviates: #N (today: field="value")]

An `annotation` names a policy, locale (`[ru]`), or extras gate (`[ja+segmenter]`) in the registry beside the test. `· boundary` marks the non-firing example every rule must carry: an input shaped like the rule's subject where its effect does NOT occur. That is usually the rule's OWN stated exception — H1's given-name title, P3's single-letter carve-out — not an input the rule never reaches, so the exception is executable rather than merely asserted. Or the rule declares `no-boundary: <reason>` instead, so skipping the boundary is a recorded decision. `deviates:` states the INTENDED output on the example line while the marker records TODAY's output and the tracking issue; the runner asserts today's output strictly, so a parser change that closes the gap fails the suite until the marker is removed in the same PR. `grep deviates:` on this file is the deviation backlog (deviations from statable rules — coverage gaps are a separate, larger category no grep can see, and contested vocabulary memberships a third, tracked as Open blocks keyed to the vocabulary set in decisions.md).

## Not in scope

- **Language detection.** The parser never infers a language from Latin-script text: transliteration destroys the signal ("Ali",
  "Van", "Bin" each belong to several languages with conflicting
  readings). Language-specific behavior is opt-in configuration. Script-conditional behavior exists only where the script itself settles the convention (see the W section).
- **Grammatical inflection.** Names inflect in many languages (vocative, genitive); this library neither produces nor consumes inflected forms. CLDR personNames draws the same line.
- **Validation.** Deciding whether a string IS a person's name is not parsing; `parse()` is total over strings and never rejects input.
- **Comparison.** matches()/comparison_key() are a value-API surface, not parsing; their design record is decisions.md#comparison-surface.

## Titles & honorifics (H)

Background: an honorific title precedes a name and is not itself part of it; it addresses or ranks the person. Most titles address by surname ("Mr. Johnson"), but a few — knighthoods, some clerical and courtesy titles — address by given name ("Sir John"). The library keeps a vocabulary of titles and, separately, of these given-name titles. What a TRAILING title-vocabulary word should do is unresolved (#316): today "John Smith Prof." keeps Prof. a name word while "Smith, Prof." reads it as a title — the two comma paths disagree, and TITLES holding ordinary surnames (king, judge, bishop) is what bars the blanket vocabulary-wins answer. Two criteria govern two different questions here. Membership in the given-name-title list follows HOW THE TITLE ADDRESSES: a title that precedes and addresses by the given name belongs (Sir, Sheikh, the Arabic honorifics الدكتور/الشيخ — which qualify even though those traditions fully retain family names). Whether an EMPTY FAMILY is correct output is the separate question, governed by surname retention: renunciation abolishes the surname, so for Swami, Guru, Baba or Lama family="" is right (#346), while rabbi and imam traditions keep surnames — "Rabbi Cohen" addresses by title and keeps family "Cohen". Conflating the two criteria either ejects the Arabic entries or sweeps in titles that break
"Rabbi Cohen".

H1. Rationale: a title normally addresses by surname, so a title
    followed by a single name word usually names the family; but a
    given-name title addresses by given name. What stands beside
    that word — a suffix, a nickname, a maiden name — does not make
    the name any longer, so it does not decide this reading.
    A title followed by exactly one name word makes that word the
    family name, whatever suffix, nickname or maiden name stands
    beside it, unless the title is a given-name title, which keeps
    it the given name.
      "Mr. Johnson"               →  family="Johnson"
      "Mrs. Garcia"               →  family="Garcia"
      "Dr. Smith née Jones"       →  family="Smith"
      "Sir John"                  →  given="John"  · boundary
    Accepted: a given-name title plus one name word leaves the
    family empty — the input names no family, and inventing one
    would be worse.
      "Sir John"                  →  family=""
    history: decisions.md#H1 · interacts: P2, P3, P5, M2, S1, S2, N1, N3 · implemented: nameparser/_pipeline/_post_rules.py

H2. Rationale: before a name, an abbreviation is almost always a
    title — "Rev.", "Ing.", "Mag." — and no vocabulary can list
    every profession's abbreviations in every language.
    An abbreviation opening the part of the name that carries the
    given name — the whole name, or the part after a family comma —
    reads as a title even when unlisted, provided it is an unbroken
    run of two or more letters ending in its one period; a bare
    initial does not, and neither does anything with interior
    periods, hyphens or digits. Where it fires, the shape outranks
    vocabulary: a period-marked opening word is a title even when
    the word is suffix vocabulary — except after a family comma,
    where a part that is nothing but suffix words is the credential
    run (C1) and the abbreviation opens nothing.
      "Rev. John Smith"           →  title="Rev."
      "Xyz. John Smith"           →  title="Xyz."
      "Smith, Major. John"        →  title="Major."
      "Esq. Smith"                →  title="Esq."
      "J. Smith"                  →  given="J."  · boundary
      "J.R. Smith"                →  given="J.R."  · boundary
    Accepted: the shape is only recognizable as an unbroken run of
    letters, so an abbreviation in a script whose letters carry
    combining vowel signs (Bengali, Devanagari) never reads as a
    title by shape — an unlisted abugida honorific stays a name
    word, and only vocabulary (#343) can recognize it.
      "প্রফেসর. Sen"              →  given="প্রফেসর."
    Accepted: before a family comma the pre-comma text is wholly the
    family name (C1), so no shape or vocabulary reading makes a
    title there.
      "Xyz. Smith, John"          →  family="Xyz. Smith"
    Accepted: after a family comma a part that is nothing but suffix
    words is the credential run (C1), which the abbreviation does
    not open: the vocabulary decides, and "Esq." is the postnominal
    it is.
      "Smith, Esq."               →  suffix="Esq."
    history: decisions.md#H2 · interacts: C1, P4 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py

H3. Rationale: compound titles are written as a run of title words,
    connectives included; a title word standing inside the name is
    just a name word.
    Successive title words at the start of the part carrying the
    given name chain into one title; a title word elsewhere in the
    name does not.
      "Asst. Vice Chancellor John Smith"  →  title="Asst. Vice Chancellor"
      "Marquess of Bath"          →  title="Marquess of Bath"
      "Morse, Det. Insp. Jane"    →  title="Det. Insp."
      "John Doctor Smith"         →  middle="Doctor"  · boundary
    Accepted: before a family comma the pre-comma text is wholly the
    family name (C1), title words included.
      "Dr. Smith, John"           →  family="Dr. Smith"
    interacts: C1 · implemented: nameparser/_pipeline/_pieces.py

## Particles & surname prefixes (P)

Background: particles ("de", "la", "van", "von", "bin") link forward to a surname and are written as part of it. Some are never anyone's given name; others ("Van", "Bin") are ordinary given names in some cultures, so the vocabulary distinguishes never-given particles from ambiguous ones, and only the never-given ones license special treatment. A separate small vocabulary binds forward to a GIVEN name instead: words like "abdul" that are not complete given names alone (P5). Which particles fall on which side of the never-given line is its own open question (#360).

P1. Rationale: a never-given particle standing alone cannot be
    someone's given name; a name that opens with one, or offers only
    one as the given name, is a surname written out in full.
    A never-given particle standing alone where the given name would
    go — or opening the name — marks the name as surname-only: the
    particle run and the name words it attaches to are the family. It
    needs another name word to attach to. The run is every particle
    in sequence, never-given and ambiguous alike ("de la Vega" is
    one group, not "de" plus a separate "la Vega"). An ambiguous particle keeps
    whatever reading its position gives it. That the particle claims
    the FAMILY rather than a given name holds under every order: a
    never-given particle is evidence about how the name is written,
    and a declared order governs only what no vocabulary has claimed
    (O4) — the same precedence the script license takes in W4.

    How MANY name words it attaches to depends on the order, and on
    which of the two positions above the particle stands in. Opening
    the name, under a family-first order, it takes exactly ONE —
    declaring that order asserts that what follows the family is not
    more surname. Opening the name under the default order, or
    standing in the given position under any order, it takes the rest
    of the name: nothing there marks where the surname ends. One name
    word means one UNIT — a particle chain (P2), a conjunction join
    (P3) or a bound given-name pair (P5) is taken whole or not at
    all. A title does not move the opening position (P4), but a
    family comma does end the question: the comma has already fixed
    the surname, so there is no positional read left for an order to
    narrow, and a particle opening the part AFTER it takes the rest
    of that part whatever order is declared. What is left over is not read by O4's rule for a whole name,
    which would make the first leftover a second family name; it is
    laid out as the positions AFTER the family in the declared order,
    the family slot being already filled.
      "de la Vega"                →  family="de la Vega"
      "Sir de Mesnil"             →  family="de Mesnil"
      "Mesnil de"  family-first   →  family="Mesnil de"
      "de Mesnil Juan"            →  family="de Mesnil Juan"
      "de Mesnil Juan"  family-first  →  family="de Mesnil"
      "de Mesnil Juan"  family-first  →  given="Juan"
      "Smith, de Mesnil Juan"  family-first  →  family="Smith de Mesnil Juan"
      "de la Vega y Santos Juan"  family-first  →  family="de la Vega y Santos"
      "ibn Awf abdul Rahman"  family-first  →  given="abdul Rahman"
      "de la Cruz Juan Carlos"  family-first-given-last  →  given="Carlos"
      "Mc Donald"                 →  family="Mc Donald"
      "de los Santos"             →  family="de los Santos"
      "van Gogh"                  →  given="van"  · boundary
    Accepted: a bare "de" stays the given name — there is nothing to
    fold into, and inventing a surname would be worse.
      "de"                        →  given="de"
    Accepted: stopping the run leaves a MIDDLE where the fold never
    left one before, so O3 has something to claim that it could not
    reach until now. The family it then reports is discontiguous in
    the input — words 1-3 plus word 5 — and renders the folded word
    first, which is R1's order, not this rule's doing.
      "de la Cruz Juan Carlos"  family-first+middle_as_family  →  family="Carlos de la Cruz"
    Accepted: only the OPENING position is this rule's subject. A
    particle chain standing inside the name is grouped normally (P2)
    and positioned by the declared order, so a family-first reading
    may report it as the given name; what the vocabulary forbids is
    the bare particle reading as a given name, not any name part
    that begins with one.
      "Juan de la Vega"  family-first  →  family="Juan"
    history: decisions.md#P1 · interacts: O3, O4, P2, P3, P4, P5, P6 · implemented: nameparser/_pipeline/_post_rules.py

P2. Rationale: a particle is written as part of the surname it
    precedes, and a title stands outside the name entirely.
    A particle joins the words after it into one name part, the
    join running until the next particle starts a group of its own,
    a trailing suffix begins — read as assign will read it (S2),
    over the pieces the chain leaves: a trailing roman numeral, or a
    bare acronym with words to spare, ends the chain as a suffix word
    does — a maiden marker takes the
    words after it (M2), or the name ends. The final group reads as
    the family name;
    earlier groups read by position. The chain begins wherever the
    name begins, and a preceding title does not move that point.
    Where P1's fold has claimed the opening, the fold decides the
    family instead — and may take only PART of the final group,
    since it counts name words and the group is one part.
      "John van der Berg"         →  family="van der Berg"
      "John van der Berg Smith"   →  family="van der Berg Smith"
      "Vincent van Gogh van Beethoven"  →  middle="van Gogh"
      "Dr. John van der Berg"     →  family="van der Berg"
      "Juan de"                   →  family="de"  · boundary
      "de la Cruz Juan Carlos"  family-first  →  family="de la Cruz"
      "John van der Berg PhD"     →  family="van der Berg"
      "John van der Berg V"       →  family="van der Berg"
      "John van der Berg V"       →  suffix="V"
      "John van der Berg Ma"      →  suffix="Ma"
      "John van der J. V"         →  family="van der J. V"  · boundary
      "Freiherr von Berg MA"      →  family="von Berg MA"
      "Freiherr von Richthofen V" →  suffix="V"  · boundary
      "John van der Berg née Jones"  →  family="van der Berg"
    Accepted: a particle of the unambiguous suffix vocabulary too
    (vd, mc) is a suffix piece to the peel, so where it opens the
    trailing run the chain stops before it as before any suffix
    word, and the peel takes it; where it continues a prefix run,
    the run takes it as a particle, as P6 reads it after a comma.
      "John Smith Mc V"           →  suffix="Mc, V"
      "John van Mc"               →  family="van Mc"
    Accepted: a caller wanting the combined double-surname reading
    (#132's ask) has it as the surnames view rather than the
    family field.
      "Vincent van Gogh van Beethoven"  →  surnames="van Gogh van Beethoven"
    history: decisions.md#P2 · interacts: P1, P4, M2, S2 · implemented: nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py

P3. Rationale: connective words ("y", "of the") bind name words into
    one name part; but a single letter in a short name is more
    likely an initial than a connective.
    A recognized connective joins its neighbors into one name part,
    connective runs included — except a single-letter connective in
    a three-word name, which stays a name word, and a single-letter
    connective written as a bare Latin capital, which reads as an
    initial and never joins. The joined part is ONE name word
    wherever another rule counts them, so a rule taking "one name
    word" takes the whole join and never half of it. The three-word
    count is of the name's own words: a maiden marker taken as one,
    and the words it takes (M2), are not among them, so a maiden
    clause does not change whether the connective joins. A marker
    left as a word (M2) is a word, and counts.
      "Juan y Eva Garcia"         →  given="Juan y Eva"
      "Jose E Maria Santos"       →  middle="E Maria"
      "Juan y Garcia"             →  middle="y"  · boundary
      "Juan y Garcia née Jones"   →  middle="y"
      "Juan and Garcia"           →  given="Juan and Garcia"
      "Juan & Garcia"             →  given="Juan & Garcia"
      "Mr. Jack and Jill"         →  family="Jack and Jill"
      "Mr. Jack Jill"             →  given="Jack"
    Both exceptions are about the written FORM, not the word: the
    three-word carve-out counts letters, so a symbol connective joins
    at any length, and it reaches every single-letter connective the
    vocabulary holds — Cyrillic и/і/й and Arabic و as well as y and
    e. Which single letters a tradition actually wants joined differs
    by language, and no locale gets its own answer today.
    Accepted: the initial veto is a LATIN shape — a Cyrillic
    capital joins ("И".isupper() is true, so this is not a
    Unicode-uppercase rule); #267's closure blessed the Cyrillic
    side, and whether the Latin-capital half should stand is #383.
      "Хосе И Мария Сантос"       →  given="Хосе И Мария"
    H1 is the counting rule that shows the one-word clause today: a
    title plus the join reads the whole join as the family, where the
    same two words unjoined are two name words and H1 does not fire.
    P1's leading run becomes the second once #395 lands — its run
    must take the "Vega y Santos" join whole or stop before it.
    history: decisions.md#P3 · interacts: H1, P1, M2 · implemented: nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py

P4. Rationale: a particle links forward from inside a name; at the
    very front there is no name yet to be inside.
    A particle in the name's leading position chains nothing: the
    words stay separate, and any surname reading the name gets
    comes from the fold (P1) or from position (O4), never from a
    join. This is why a title before a leading particle changes
    nothing (the title is not a name word), and why "Van Johnson"
    is a given-name reading at all. An unlisted abbreviation before
    the particle is as transparent as a listed title, since assign
    reads it as one (H2).
      "Van Johnson"               →  given="Van"
      "Sir de Mesnil"             →  pieces=[["Sir"], ["de"], ["Mesnil"]]
      "Xyz. van Johnson"          →  given="van"
      "John van der Berg"         →  pieces=[["John"], ["van", "der", "Berg"]]  · boundary
    history: decisions.md#P2 · interacts: P1, P5, H2 · implemented: nameparser/_pipeline/_group.py

P5. Rationale: some given-name words are incomplete alone — "abdul"
    is a bound form that the next word completes.
    A recognized bound given-name word joins the word after it into
    one given name. It needs a name word to spare, so two name words
    alone do not join — the second is the family name — except after
    a family comma, where the family is already fixed, or after a
    given-name title, which asserts that a given name follows (H1):
    there the two words join and the name has no family — two name
    WORDS, so neither a particle chain (P2), which is the family
    name, nor a suffix word is joined. The title run is read as one
    key, as H1 reads it. Where the join fires, a bound word that is
    also a particle is read as the bound word: the join outranks the
    leading-position reading (P4) and no fork is reported; where the
    reserve blocks the join, P4's reading and its fork stand. Where
    the word
    is BOTH bound-given and suffix vocabulary, position decides and
    both readings survive: leading, it is the bound word; trailing,
    it is the suffix (S2). In the given slot after a family comma the
    suffix reading wins. The marker and the words it will take are
    not among the words to spare: they leave the name, so counting
    them asks the question about a name that will not exist. The join
    never absorbs a marker standing as a word of its own — a marker
    is not a name word (M2) — nor a word of the unambiguous suffix
    vocabulary (S2), wherever position will then place it; a bare
    ambiguous acronym is a name word wherever the peel does not take
    it; a marker left as a word that a particle join (P2) has already
    taken travels with that join. A title word standing in the name
    is a name word (H3) and joins like one, and so is a particle the
    chain has not taken (P2) — unless it is of the unambiguous
    suffix vocabulary too (vd, mc), which the join declines as the
    suffix piece it is:
    the pair is a given name whatever tag the word carried, and
    after a family comma the join runs before the trailing
    particle's attachment (P6) sees the name. What
    there is to spare is what
    assign will leave: the join is tried on the pieces as it would
    leave them, assign's trailing peel (S2) is read over that, and
    the name words it leaves are the words to spare — a trailing
    roman numeral, or a bare acronym the peel takes, is no
    word to spare. The join joins two name words into one and
    changes no suffix reading: a word the peel reads as a suffix
    unjoined must read so joined, or the join declines. After a
    family comma the family is fixed and the joined pair is the given
    whatever follows, so the reserve there reads no peel: the join
    stands whenever the word after the bound word is a name word.
      "abdul salam ahmed salem"   →  given="abdul salam"
      "abd Allah Smith"           →  given="abd Allah"
      "Salam, abd Allah"          →  given="abd Allah"
      "abd Allah"                 →  given="abd"
      "Smith, Abd"                →  suffix="Abd"
      "mohamad ali smith"         →  given="mohamad"  · boundary
      "Sheik abdul salam"         →  given="abdul salam"
      "Sheik abdul salam Jr"      →  given="abdul salam"
      "Sheik Abu Bakar"           →  given="Abu Bakar"
      "Abu Bakar Salim"           →  given="Abu Bakar"
      "Dr. abdul salam"           →  family="salam"  · boundary
      "Sir abdul van der Berg"    →  family="van der Berg"  · boundary
      "Sheik abdul Jr Smith"      →  given="abdul"  · boundary
      "Abu Bakar"                 →  given="Abu"  · boundary
      "abdul Smith V"             →  family="Smith"
      "abdul Smith V"             →  suffix="V"
      "abdul Smith Jr V"          →  family="Smith"
      "abdul Smith Jr Ma"         →  family="Smith"
      "abdul Smith Jr Ma"         →  suffix="Jr, Ma"
      "abdul Smith Ma"            →  suffix="Ma"
      "abdul Smith Berg Ma"       →  family="Berg"  · boundary
      "abdul Sir Smith Berg"      →  given="abdul Sir"
      "Berg, abdul van"           →  given="abdul van"
      "Berg, abdul vd"            →  family="vd Berg"
      "abdul Jr Smith Berg"       →  given="abdul"
      "abdul Jr Smith Berg"       →  middle="Jr Smith"
      "abdul Ph. D. Smith Berg"   →  suffix="Ph. D."
      "abdul V Smith"             →  given="abdul V"  · boundary
      "abd Berg née Jones"        →  family="Berg"
      "abd Allah Smith née Jones" →  given="abd Allah"
      "abd née Jones"             →  given="abd"
      "Berg, abd née Jones"       →  suffix="abd"
    Accepted: after a family comma the join stands though, unjoined,
    assign would read the word it takes as the suffix — the family
    is fixed there and the pair is the given; and a bare ambiguous
    acronym the peel does not take joins as any name word does.
      "Berg, abdul V"             →  given="abdul V"
      "abdul Ma Smith"            →  given="abdul Ma"
    Accepted: a given-name title plus a bound pair leaves the family
    empty, as H1 accepts for "Sir John" — the input names no family.
    Under a family-first order the joined pair is the family and the
    given name is empty instead, as "Sir John" reads there: the join
    is order-blind, and H1's exemption never runs under that order.
      "Sheik abdul salam"         →  family=""
      "Sheik abdul salam"  family-first  →  family="abdul salam"
      "Sheik abdul salam"  family-first  →  given=""
      "Sheik abdul salam"  family-first-given-last  →  family="abdul salam"
    history: decisions.md#P5 · interacts: S2, M2, H1, P2, P4, P6 · implemented: nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py

P6. Rationale: a particle ending the name has nothing to link
    forward to, so it is not doing a particle's work there. A
    never-given particle in that position cannot be a name at all
    and must belong to the family written beside it; an ambiguous
    particle could genuinely be the name (Vietnamese "Van"), and
    after a comma there is no signal that separates the two
    readings. Dutch and Flemish names are listed exactly
    this way ("Beethoven, Ludwig van"), the tussenvoegsel trailing
    the given name but belonging to the surname.
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
    often than the decoration it collides with.
      "Jong, Anke de"             →  family="de Jong"
      "Beethoven, Ludwig van"     →  family="van Beethoven"
      "Berg, Jan vd"              →  family="vd Berg"
      "Berg, Jan van der"         →  family="van der Berg"
      "Vega, Juan de la"          →  family_particles="de la"
      "Beethoven, Ludwig van"     →  family_base="Beethoven"
      "Beethoven, Ludwig van"     →  family_particles="van"
      "Nguyen, Van"               →  given="Van"  · boundary
    Accepted: an ambiguous particle attaches on the same terms as a
    never-given one, so a Vietnamese name written in this listing
    loses its given name — but only in the UNACCENTED
    transliteration. Vân carries a diacritic and is not particle
    vocabulary, so the correctly spelled name never reaches this
    rule. It is the ASCII spelling that collides, and there the two
    traditions write the same string.
      "Nguyen, Thi Van"           →  family="Van Nguyen"
      "Nguyễn, Thị Vân"           →  family="Nguyễn"
    Accepted: no ambiguity is reported for that collision, which A1
    would call for. The fork is decided here, and assign's emitter is
    scoped to the no-comma shapes on the reasoning that a comma has
    fixed the family — true of the family, not of the particle behind
    it. Tracked at #405.
    Accepted: the colliding spelling has a format that reads
    correctly, and it is ONE order, not both: FAMILY_FIRST still
    sends the given name to the middle, and only
    FAMILY_FIRST_GIVEN_LAST recovers it.
      "Nguyen Thi Van"  family-first-given-last  →  family="Nguyen"
      "Nguyen Thi Van"  family-first-given-last  →  given="Van"
      "Nguyen Thi Van"  family-first  →  middle="Van"
    Accepted: without a family comma the name's written shape is not
    settled — "Jong Anke de" may be a misformatted listing, and a
    bare "Jong de" may be a given name beside a particle — so the
    attachment is scoped to the comma form, and the comma-less
    shapes keep their positional reading.
      "Jong Anke de"              →  family="de"
    Accepted: the precedence over S2 is stated for the shape, so it
    sweeps in every word that is both particle and suffix
    vocabulary — today vd, do and mc. Only vd's reading was
    weighed; mc inherits it, which is the shape's cost and is
    tracked with the other contested memberships. `do` sits in the
    AMBIGUOUS acronym half and was already read as a name word
    there, so the precedence decides nothing for it.
    Accepted: a bound given word ahead of the trailing particle takes
    it as its pair first (P5), so the attachment never sees it —
    unless the particle is of the unambiguous suffix vocabulary too
    (vd, mc), which the join declines and the attachment then takes.
      "Berg, abdul van"           →  given="abdul van"
      "Berg, abdul vd"            →  family="vd Berg"
    history: decisions.md#P6 · interacts: C1, P1, S2, P5 · implemented: nameparser/_pipeline/_post_rules.py

## Suffixes: generational & credentials (S)

Background: what follows a name is one of two different things — generational suffixes (Jr., III), which attach to the name itself, and credentials (PhD, MD, MBA), which are earned attachments. All vocabulary sets match one written word at a time: a multi-word entry can never match anything and is warned about at configuration (the eight that shipped dead for years are the Excluded story in decisions.md). CLDR personNames keeps them as separate fields (`generation`, `credentials`) and formats them differently; this library currently reports both in one `suffix` field, a merge #326 examines. The vocabulary is largely split already: a generational word list and a credential acronym list, plus a short list of acronyms that are also ordinary names (MA, BA) and so are AMBIGUOUS as bare words.

S1. Rationale: brackets set off more than nicknames — credentials
    are routinely written parenthesized after a name, and a
    credential is recognizable by its form.
    A bracketed clause whose content is suffix-shaped is not a
    nickname: the brackets are dropped and the content reads exactly
    as if written bare.
      "Andrew Perkins (MBA)"      →  suffix="MBA"
      "Andrew Perkins (Andy)"     →  nickname="Andy"  · boundary
    implemented: nameparser/_pipeline/_extract.py

S2. Rationale: generational suffixes and credentials are recognized
    by vocabulary; an acronym that is also an ordinary name is only
    unmistakably a credential when its periods are written.
    A trailing word of the suffix vocabulary reads as a suffix —
    generational forms and credential acronyms alike, and an
    ambiguous acronym written with its periods, one after each
    letter, counts unambiguously; a single trailing period is the
    abbreviation shape any word can wear and does not. A
    BARE ambiguous acronym is consumed only when the name has words
    to spare — as the second of two words it stays the family
    name — and either reading carries the ambiguity flag.
      "John Smith Jr."            →  suffix="Jr."
      "John Smith M.A."           →  suffix="M.A."
      "John Smith PhD"            →  suffix="PhD"
      "John Ma"                   →  family="Ma"  · boundary
      "Jack Ma."                  →  family="Ma."  · boundary
    Accepted: with words to spare, a bare ambiguous acronym reads
    as a suffix even beside an East Asian surname it more likely
    belongs to; and an unambiguous suffix is consumed even when
    that leaves no family name at all.
      "Jack Wei Ma"               →  suffix="Ma"
      "Jack Wei Ma"               →  ambiguities=("suffix-or-name",)
      "Smith Jr."                 →  family=""
    implemented: nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py

S3. Rationale: credentials are often written run together with
    periods; the chunks between the periods are what carry the
    vocabulary.
    A word with interior periods reads as a suffix when any of its
    period-separated chunks is suffix vocabulary — any chunk, which
    is looser than it sounds, since single letters can be Roman
    numerals.
      "John Smith J.u.n.i.o.r."   →  suffix="J.u.n.i.o.r."
      "John Smith Q.W.E.R.T."     →  family="Q.W.E.R.T."  · boundary
    implemented: nameparser/_pipeline/_vocab.py

## Nicknames & quoted names (N)

Background: a nickname is written beside the formal name, set off by quotes or brackets. Quotation conventions vary by language („…“,
«…», “…”), several share characters — one convention's closer is
another's opener — and the straight apostrophe doubles as a quotation mark and as a letter-like mark inside names (O'Connor). Which pairs delimit nicknames is caller configuration.

N1. Rationale: a quoted or bracketed clause beside a name is an
    informal alias, not part of the name.
    A clause enclosed by a configured nickname delimiter pair reads
    as the nickname and is lifted out of the name; an empty
    enclosure is simply dropped.
      "Andrew (Andy) Perkins"     →  nickname="Andy"
      "Jean 'JD' Smith"           →  nickname="JD"
      "Anna () Smith"             →  nickname=""  · boundary
    implemented: nameparser/_pipeline/_extract.py

N2. Rationale: only a mark standing at word boundaries is quoting;
    anywhere else it is part of the word.
    A quote whose open and close are the same character opens only
    at a word start and closes only at a word end, so an apostrophe
    inside or at the end of a word is literal. Between conventions
    that share a character, position in the text decides: the
    leftmost valid opener wins — and a dangling-open report is
    suppressed where its character sits inside another pair's
    successful match, being literal content there rather than an
    imbalance (A1 depends on that filter).
      "Sean O'Connor"             →  family="O'Connor"
      "Hans „Erster“ und “Zweiter” Müller"  →  nickname="Erster Zweiter"
      "Mari' Aube'"               →  family="Aube'"  · boundary
    history: decisions.md#N2 · implemented: nameparser/_pipeline/_extract.py

N3. Rationale: a person set down as a nickname plus one name word is
    being identified by surname.
    A name that is only a nickname and one name word reads that word
    as the family name; with two or more name words the ordinary
    positional reading applies.
      "'Smitty' Jones"            →  family="Jones"
      "'Smitty' John Jones"       →  given="John"  · boundary
    Accepted: the count does not set suffixes aside, so a nickname
    plus one name word plus a suffix reads the name word as given
    and leaves the family empty. A title counts against the count
    too, but H1 then reads the title-plus-one-word name that is
    left, so the family is named after all — unless the title is a
    given-name title, which keeps the word in `given` and leaves no
    family, exactly as it does anywhere else.
      "'Smitty' Jones Jr."        →  family=""
      "'Smitty' Dr. Jones"        →  family="Jones"
      "'Smitty' Sir John"         →  given="John"
    history: decisions.md#N3 · interacts: H1 · implemented: nameparser/_pipeline/_assign.py

## Maiden names (M)

Background: a maiden name is written beside the current name, set off by a marker word or by enclosure. Markers are attested across French née/né, German geb./geborene, Dutch geboren, Czech/Slovak rozená (the abbreviation roz. is deliberately not shipped -- it collides with the English diminutive Roz), Scandinavian født/fødd/född, Russian урожд. (both ё and е spellings), and Japanese 旧姓 — both grammatical genders where attested. Japanese more often writes the marker with a fullwidth colon (旧姓：佐藤), which is no separator, so marker and name arrive as a single word. Which enclosures mean "maiden" rather than "nickname" is a caller convention, so the maiden reading of a delimiter pair is opt-in — except where the clause announces itself. A clause of two words or more led by a marker word has said which convention it means, and reads as the maiden name inside a nickname pair as well (M3); a lone marker word has not, and neither has one the colon spelling above glues to the name.

M1. Rationale: an enclosure the caller has declared to mean maiden
    holds the former family name; a recognized marker word inside it
    marks the clause and is not itself part of the name.
    With a delimiter pair configured for maiden names, its enclosed
    clause reads as the maiden name — unless the content is
    suffix-shaped, which S1 takes first — a leading recognized
    marker word inside a multi-word clause being dropped; a one-word
    clause keeps its word, which may itself be a surname (Nee).
    Clauses are independent: two enclosures read as one maiden name,
    each dropping or keeping its own marker. A pair configured for
    both maiden and nickname reads maiden. Configuring the pair is
    what this rule needs for a clause that does not announce itself
    — markerless content, and a lone marker word alike; a clause of
    two words or more led by a recognized marker reads as the maiden
    name inside a nickname pair as well (M3).
      "Jane Smith (née Jones)"  maiden-parens  →  maiden="Jones"
      "Jane Smith (Nee)"  maiden-parens        →  maiden="Nee"  · boundary
      "Jane Smith (Nee) (Jones)"  maiden-parens  →  maiden="Nee Jones"
      "Andrew Perkins (MBA)"  maiden-parens  →  suffix="MBA"  · boundary
    history: decisions.md#M1 · interacts: S1, M2, M3 · implemented: nameparser/_pipeline/_extract.py, nameparser/_pipeline/_group.py

M2. Rationale: a maiden marker announces that what follows it is the
    former family name; the marker is an announcement, not a name.
    A recognized maiden marker standing after at least one name
    word takes the words after it — up to any suffix word, or the
    trailing roman numeral assign reads as the suffix (S2), both as
    written and as the take would leave the name, the word before
    the numeral being then the word before the marker — as the
    maiden name, and
    the marker itself is dropped. A marker
    with nothing after it, or nothing before it, is just a word.
    A marker taken this way also bounds a particle join arriving from
    its left (P2), so the family name's particles stop at the marker
    instead of absorbing it; a marker left as a word bounds nothing.
    Where the bound leaves a family of nothing but particles, they
    are not in particle position and read as ordinary words (R2).
      "Jane Smith née Jones"      →  maiden="Jones"
      "Jane née Jones Smith"      →  maiden="Jones Smith"
      "Jane Smith née Jones PhD"  →  suffix="PhD"
      "John née Jones Smith V"    →  maiden="Jones Smith"
      "John née Jones Smith V"    →  suffix="V"
      "Jane Smith née V"          →  suffix="V"
      "J. née Jones Smith V"      →  maiden="Jones Smith V"  · boundary
      "Jane née Jones J. V"       →  maiden="Jones J. V"  · boundary
      "Jones née"                 →  family="née"  · boundary
      "née Jones"                 →  family="Jones"  · boundary
      "Jane van der Berg née Jones"  →  maiden="Jones"
      "Jane de la née Jones"         →  family="de la"
      "Jane van der Berg née"        →  family="van der Berg née"
      "Jane van der Berg née PhD"    →  family="van der Berg née"
      "Jane van der Berg née y Jones"  →  maiden="y Jones"
      "van der Berg, abdul née Jones"  →  maiden="Jones"
    Accepted: the fullwidth-colon spelling arrives as one word, so
    the marker inside it goes unrecognized; #317 tracks whether it
    should peel.
      "山田 花子 旧姓：佐藤"       →  maiden=""
    Accepted: a marker straight after a comma is post-comma given
    text, not a marker.
      "Jane Smith, née Jones"          →  maiden=""
    Accepted: the marker reads the words as written, so a suffix word
    inside the maiden name ends it even where a connective beside it
    would have bound the two into one name word (P3); the connective
    then builds a family name out of what is left.
      "Jane née Jr y Jones"            →  maiden=""
    Accepted: a bare acronym the peel would take with words to spare
    is maiden text all the same — the count it needs includes the
    very words the marker removes, so the reading is left to assign.
      "John née Jones Smith Ma"        →  maiden="Jones Smith Ma"
    history: decisions.md#M2 · interacts: P2, P3, P5, R2, M1, S2, H1 · implemented: nameparser/_pipeline/_group.py

M3. Rationale: an enclosure says nothing about whether it means
    maiden, but a recognized marker word inside it does — the clause
    announces itself, so the caller does not have to declare the
    pair.
    A bracketed clause whose content opens with a recognized marker
    word and carries a word after it reads as the maiden name,
    whichever bucket the enclosing pair sits in — unless the content
    is suffix-shaped, which S1 takes first — the marker itself
    dropped, as M1 drops it. A marker with no word after it is just
    a word in brackets, and so is a marker no separator divides from
    the name, the fullwidth-colon spelling M2 records. Where the
    pair is already configured for maiden names M1 governs and this
    adds nothing. Being keyed on the content rather than on the
    pair, this reaches a nickname pair's clause too, and M1's
    independence then governs what it produces: where a marker-led
    clause stands beside another marker-led clause, both read as
    maiden and join into one maiden name, leaving no nickname.
      "Jane Smith (née Jones)"    →  maiden="Jones"
      "Jane (née Jones) Smith"    →  family="Smith"
      "Jane Smith (née)"          →  nickname="née"  · boundary
    Accepted: the word taken after the marker is not tested for
    being a name word, so unlike M2's bare take this one does not
    stop at a suffix word — the same two words read one way
    bracketed and another way bare.
      "Jane Smith (née V)"        →  maiden="V"
    history: decisions.md#M3 · interacts: M1, M2, S1, N1 · implemented: nameparser/_pipeline/_extract.py

## Commas & structure (C)

Background: a comma in a name signals one of two conventions — the listing form "Family, Given" or trailing credentials "Name, PhD" — and which is meant can only be judged from what stands after the first comma. Recognizing a credential run is by nature a vocabulary judgment, so this is the one structural decision that consults the suffix word lists. Which characters COUNT as the comma is part of the rule: the Arabic comma (U+060C) and the fullwidth comma (U+FF0C) both signal the listing form, while the ideographic comma (U+3001) is not a name-structure comma at all (#265).

C1. Rationale: a credential run after the comma means the name is in
    natural order with suffixes appended; anything else after the
    comma means the listing form.
    With a comma present, the name reads as trailing suffixes when
    the part after the first comma is entirely suffix words and more
    than one word precedes the comma; otherwise it reads as the
    listing form, the part before the comma being the family name.
    Only the part after the first comma decides. Both modes consult
    the vocabulary alone; by default a recognized suffix word counts
    even written like an initial ("V."), while strict mode vetoes
    initial-shaped words. In the listing form the part after the
    comma is still read for what it is: a part that is nothing but
    suffix words is the credential run and reads as suffixes, whole
    — the slot after a family comma is postnominal position, so the
    vocabulary's verdict comes before any title reading of the same
    word — and a part that holds no name word at all, titles and suffixes
    only, fixes no family boundary, so a part before the comma with
    more than one name word keeps its positional read, order and
    all. A name word in the part after the comma makes it the
    given name, with titles before it and suffixes after.
    A one-character suffix word — the only kind a reader could take
    for an initial — is read by what stands before it. Behind
    another suffix it is describing that suffix and continues the
    run, written with a period or without, an initial being no shape
    anyone writes there; behind a name word it is the generation
    only when written bare, a period marking it the abbreviation of
    a name and so a middle initial. Longer suffix words are not in
    question either way, and the strict knob above still vetoes the
    initial-shaped ones, so the run ends at them there.
      "Smith, John"               →  family="Smith"
      "سلمان، محمد"               →  family="سلمان"
      "田中、太郎"                 →  family=""
      "John Smith, PhD"           →  suffix="PhD"
      "John Smith, V."            →  suffix="V."
      "John Smith, V."  strict-comma-suffixes  →  family="John Smith"
      "Smith, PhD"                →  family="Smith"  · boundary
      "Smith, PhD"                →  suffix="PhD"
      "Smith, Jr."                →  suffix="Jr."
      "Smith, Sr."                →  suffix="Sr."
      "Smith, PSM I"              →  suffix="PSM I"
      "Smith, PSM I."             →  suffix="PSM I."
      "Smith, PSM I."  strict-comma-suffixes  →  suffix="I."
      "Smith, John V."            →  middle="V."
      "Smith, John PhD I."        →  suffix="PhD, I."
      "Smith, John V"             →  suffix="V"  · boundary
      "Smith, Ph. D. Jr."         →  suffix="Ph. D. Jr."
      "Smith, MD PhD"             →  suffix="MD PhD"
      "Smith, Dr."                →  title="Dr."
      "Smith, Dr. Jr."            →  suffix="Jr."
      "John Smith, Mr."           →  given="John"
      "John Smith, Mr."           →  family="Smith"
      "John Smith, Mr. Jr."       →  given="John"
      "Smith Jr., Mr."            →  family="Smith"  · boundary
      "John Smith, Jones"         →  family="John Smith"
    Accepted: a word of both the title and the unambiguous suffix
    vocabulary reads as the postnominal after a family comma in
    every spelling, the honorific's too — position decides for the
    duals, and the slot is postnominal.
      "Smith, Ms."                →  suffix="Ms."
      "Smith, Ms. Jane"           →  title="Ms."
    Accepted: a title-only part after a one-word family keeps the
    family whole, and a glued honorific in it stays glued — the
    honorific peel (W3) runs on the other structures, before the
    comma is read; a credential after the comma still frees it.
      "田中さん, Dr."              →  family="田中さん"
      "田中さん, PhD"              →  suffix="さん, PhD"
    Accepted: a delimiter core the policy names (T1) is a word here,
    not structure — v1 applied the delimiter to the suffix-comma
    form alone, and that limitation is kept as parity: "Smith, RN -
    CRNA" reads given "RN" under the policy as without it.
      "John Smith, LEED AP"       →  family="Smith"  deviates: #291 (today: family="John Smith")
    history: decisions.md#C1 · interacts: H2, P6 · implemented: nameparser/_pipeline/_segment.py, nameparser/_pipeline/_assign.py, nameparser/_pipeline/_group.py

C2. Rationale: text beyond the recognized comma parts should be
    taken in without silent guessing.
    Parts beyond the second are consumed as suffixes either way; a
    non-empty extra part that is not entirely suffix words is
    flagged as a structural ambiguity rather than rejected — parsing
    never fails on content. An empty part between doubled commas is
    consumed silently.
      "John Smith, MD, Bart"      →  suffix="MD, Bart"
      "John Smith, MD,, Jr."      →  suffix="MD, Jr."  · boundary
    history: decisions.md#C1 · implemented: nameparser/_pipeline/_segment.py

## Name order (O)

Background: written name order varies by convention: given-first (the library's default reading), family-first, and family-first with the given name last (Vietnamese, where the person is called by the last element, given names are frequently two syllables — the given_names view stays correct wherever the internal boundary falls — and quốc ngữ is Latin script, so no native-script signal exists at all). The order is declared by the caller or a locale pack, never detected — but a few conventions leave a recognizable trace in the name itself. Patronymics are one: East Slavic names carry a father's-name derivative with distinctive endings between given and family, and Turkic names use a standalone marker word ("oglu" son-of, "qizi" daughter-of) after the father's name. Where such a trace is present and unambiguous, an opted-in parser can restore the intended reading from a family-first listing.

O1. Rationale: an East Slavic name written family-first still shows
    its patronymic — the distinctive ending identifies which word is
    the patronymic, and the patronymic sits next to the given name.
    With East Slavic patronymic handling active and no comma in the
    name, a name of exactly three name words — titles, suffixes and
    nicknames aside — whose last name word carries a patronymic
    ending and whose middle name word does not reads as family-first:
    the words are restored to given, patronymic, family. A middle
    word that also carries the ending blocks the reading, because
    the surname itself may be patronymic-derived.
      "Сидоров Иван Петрович"  [ru]  →  family="Сидоров"
      "Sidorov Ivan Petrovich Jr."  [ru]  →  family="Sidorov"
      "Иван Петрович Абрамович"  [ru]  →  family="Абрамович"  · boundary
    history: decisions.md#O1 · implemented: nameparser/_pipeline/_post_rules.py

O2. Rationale: a Turkic patronymic marker is a separate word that
    follows the father's name; a four-word name ending in one is a
    family-first listing.
    With Turkic patronymic handling active and no comma in the name,
    a name of exactly four name words — titles, suffixes and
    nicknames aside — ending in a standalone patronymic marker reads
    family-first: the first name word is the family name, and the
    marker stays beside the father's name in the middle.
      "Ali Ahmad Vali oglu"  [tr_az]  →  family="Ali"
      "Ali Ahmad Vali oglu Jr."  [tr_az]  →  family="Ali"
    Accepted: any other count of name words keeps its positional
    reading, even when that leaves the marker itself in a name
    field.
      "Ali Ahmad oglu"  [tr_az]  →  family="oglu"  · boundary
    history: decisions.md#O2 · implemented: nameparser/_pipeline/_post_rules.py

O3. Rationale: several traditions write compound family names
    unmarked, so that every word after the given name belongs to the
    family name.
    With compound-family handling active, every middle word joins
    the family name and is rendered before it; no word is a middle
    name.
      "Hassan Mohamad Ali"  middle_as_family  →  family="Mohamad Ali"
      "Hassan Mohamad Ali"                    →  family="Ali"  · boundary
    implemented: nameparser/_pipeline/_post_rules.py

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
    implemented: nameparser/_pipeline/_assign.py

## Scripts & writing systems (W)

Background: script-conditional behavior is permitted exactly where the writing system itself — not statistics about it — settles the convention; a language can never be inferred from Latin-script text, because transliteration destroys the signal. The facts this section builds on: Chinese and Japanese both write the family name first in native script, so the script settles the order without knowing the language. Hangul is written by exactly one language and Korean family names are a small closed census set. Han text does not identify its language — a Chinese surname list would divide Japanese 高橋一郎 as 高 + 橋一郎 — which is why Han division is opt-in and there is no Korean pack to opt into. Hiragana never transcribes a foreign name (transcriptions are katakana alone), so kanji-plus-kana is a Japanese name in Japanese order, while wholly-katakana is predominantly a transcribed foreign name already in given-first order. Real Chinese text is unspaced (毛泽东); the spaced 毛 泽东 is an artifact. A fuller narrative lives in docs/usage.rst's East Asian section.

W1. Rationale: hangul is monoglot Korean and its surnames are a
    closed census set, so an unspaced hangul name divides at a
    certain point; Han carries no such certainty by default.
    An undivided word in the family position of a name written in
    an activated script divides after a recognized surname, the
    longest recognized surname first; where the vocabulary
    recognizes nothing, an optional segmenter may divide instead,
    and with neither the word stays whole rather than divide in a
    wrong place. Korean division is active by default; Han division
    is opt-in.
      "김민준"                    →  family="김"
      "남궁민수"                  →  family="남궁"
      "남궁민수 지훈"             →  family="남궁"
      "毛泽东"                    →  family="毛泽东"  · boundary
      "毛泽东"  [zh]              →  family="毛"
      "高橋一郎"  [zh]            →  family="高"
    Accepted: a name the interpunct divides is already divided in
    the sense that matters — division stands down entirely there,
    vocabulary and segmenter alike (#298; decisions.md#T3).
      "安东尼·陈志明"  [zh]        →  family="陈志明"
    history: decisions.md#W1 · implemented: nameparser/_pipeline/_script_segment.py

W2. Rationale: some East Asian honorifics glue directly onto the end
    of the name (田中さん); a glued word peels off only if it could
    never itself end a name, so the listed vocabulary carries its
    own license and needs no other gate.
    A listed honorific glued to the end of the name's last name
    word splits off once and reads as a suffix. The split-off
    crosses a family comma and ignores surrounding punctuation, but
    never treats a part that is not name text as the name's end.
      "田中さん"                  →  suffix="さん"
      "김, 민준씨"                →  suffix="씨"
      "田中さん, V."              →  suffix="さん"
      "马丁·路德·金씨"            →  suffix="씨"
      "김지양"                    →  suffix=""  · boundary
      "王君"                      →  family="王君"  · boundary
    history: decisions.md#W2 · implemented: nameparser/_pipeline/_script_segment.py

W3. Rationale: a family name declared by a comma is the writer's
    own division, and re-dividing it would invent a boundary nobody
    drew.
    Under a family comma the pre-comma text is the family by
    declaration and never divides, and the post-comma side is given
    text with no family to find; only the honorific split-off (W2)
    crosses the comma, an honorific being no part of the name on
    either side. A segmenter — unlike the vocabulary, which ignores
    spacing but not the interpunct (W1's Accepted) — is consulted
    only for a name whose written form is wholly undivided, a
    spaced honorific counting as a written division.
      "남궁민수"                  →  family="남궁"
      "지훈, 남궁민수"            →  given="남궁민수"
      "남궁민수, 지훈"            →  family="남궁민수"  · boundary
    history: decisions.md#W3 · implemented: nameparser/_pipeline/_script_segment.py

W4. Rationale: Chinese, Japanese and Korean all write the family
    name first in native script — the script settles the order
    without knowing the language — while a wholly-katakana name is
    predominantly a transcribed foreign name already in its source
    order.
    A name written wholly in one East Asian script, or in the
    kana-licensed Japanese repertoire, reads family-first whatever
    order the caller declared; a wholly-katakana name keeps the
    declared order.
      "김 민준"                   →  family="김"
      "山田 太郎"                 →  family="山田"
      "高橋 みなみ"               →  family="高橋"
      "マイケル ジャクソン"        →  given="マイケル"  · boundary
    Accepted: a name the interpunct divides keeps its source order —
    the divider itself marks a transcription (T3) — so the override
    stands down there; the katakana middle dot (T2) carries no such
    signal, so a name it divides still reads by the script license.
      "毛·泽东"                   →  given="毛"
      "威廉・莎士比亚"            →  family="威廉"
    history: decisions.md#W4 · interacts: T3 · implemented: nameparser/_pipeline/_assign.py

## Tokens, initials & punctuation (T)

Background: every parsed name part is an exact piece of the input, located by its position — nothing rewrites the text before parsing. Some punctuation is a name divider only by convention of a particular writing system: Japanese writes name parts with a middle dot between them (マイケル・ジャクソン, 姓・名), while U+00B7 is both the Chinese divider for transcribed foreign names and the Catalan punt volat interior to legitimate words (Gal·la).

T1. Rationale: a character that carries no name content (emoji, an
    invisible directionality control) stands between words, not
    inside them.
    A name splits at whitespace and — unless the caller opts to
    keep them — at ignorable characters: an ignorable character
    separates its neighbors and never joins them.
      "John😀Smith"                →  family="Smith"
      "John😀Smith"  keep-emoji    →  given="John😀Smith"  · boundary
    history: decisions.md#T1 · implemented: nameparser/_pipeline/_tokenize.py

T2. Rationale: the katakana middle dot exists to divide name parts
    and appears in no native name.
    The katakana middle dot and its halfwidth twin divide a name
    like whitespace, always.
      "マイケル・ジャクソン"        →  given="マイケル"
      "高橋・一郎"                 →  family="高橋"
    no-boundary: the separation is unconditional; the
    context-sensitive interpunct is T3's subject.
    implemented: nameparser/_pipeline/_tokenize.py

T3. Rationale: U+00B7 is two marks in one codepoint — the Chinese
    间隔号 dividing a transcribed foreign name, and the Catalan punt
    volat interior to words.
    The interpunct divides a name only between two characters of a
    classified East Asian script; anywhere else it is part of the
    word.
      "威廉·莎士比亚"              →  family="莎士比亚"
      "Gal·la Serra"              →  given="Gal·la"  · boundary
    history: decisions.md#T3 · implemented: nameparser/_pipeline/_tokenize.py

## Ambiguity & tie-breaking (A)

Background: some name strings are genuinely ambiguous — the same written shape carries two readings ("Van Johnson": given name or particle?), or the text's structure is malformed. Parsing never fails and never silently discards; it completes on the best reading and says what it was unsure of.

A1. Rationale: a caller can only act on doubt that is reported.
    Parsing never fails on any input: where the text's structure or
    a word's reading is genuinely uncertain, the parse completes on
    the best reading and carries an ambiguity report naming the
    doubt.
      "Van Johnson"               →  ambiguities=("particle-or-given",)
      "Jane „JD Smith"            →  ambiguities=("unbalanced-delimiter",)
      "John Smith, MD, Bart"      →  ambiguities=("comma-structure",)
      "John Smith"                →  ambiguities=()  · boundary
    Accepted: the one exception to totality is a user-supplied
    segmenter's own error, which propagates — a user-code error is
    not a content error. (Needs the optional extra to demonstrate,
    so no example line.)
    implemented: nameparser/_pipeline/_state.py

A2. Rationale: an input with no name content names nobody, and
    saying so beats inventing fields from punctuation.
    A name with no name content parses to the empty name — every
    field empty, false as a boolean — while ambiguities born from
    its punctuation survive on the empty result.
      ".,"                        →  family=""
      "("                         →  ambiguities=("unbalanced-delimiter",)
      "John . Smith"              →  family="Smith"  · boundary
    history: decisions.md#A2 · implemented: nameparser/_pipeline/_assemble.py

## Rendering & views (R)

Background: parsing produces words with roles; every string a caller reads is assembled from those words on request. Nothing about rendering changes the parse, and nothing about reading a field mutates anything. The default view renders '{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}' — the choice and its declined née-template alternative are decisions.md#render-default.

R1. Rationale: a field is a way of reading the parse, not a stored
    string.
    Every field is a view computed from the parsed words at read
    time, joining its words in written order — except folded family
    words — O3's fold and, since #379, P6's attached tussenvoegsel —
    which render before the rest of the family wherever they stood in
    the string.
    Words are separated as the writer separated them. The suffix view
    is the one place this is visible, because it is the only field
    that can hold parts the writer comma-separated: a run of
    post-nominals written with spaces renders with spaces, and one
    written with commas keeps them.
      "Dr. Juan Q. Xavier de la Vega III"  →  family="de la Vega"
      "Hassan, Mohamad Ahmad Ali"  middle_as_family  →  family="Ahmad Ali Hassan"
      "Hassan, Mohamad Ahmad Ali"          →  family="Hassan"  · boundary
      "Smith, MD PhD"                      →  suffix="MD PhD"
      "John Smith, MD, Bart"               →  suffix="MD, Bart"
    history: decisions.md#C1 · implemented: nameparser/_types.py

R2. Rationale: callers need the surname with and without its
    particles — sorting wants "Vega", display wants "de la Vega".
    The family name splits into further views: the base (the family
    without its leading particles) and the particles themselves. A
    name part whose every word is particle vocabulary is a part where
    none of them is doing a particle's work — nothing joins them to a
    name — so they read as ordinary name words: they anchor the base
    and leave the particles view. "Every word", not "standing alone":
    a two-particle run has neither word alone and both are name words
    there. Position decides that, not vocabulary; whether the word is
    borne as a surname somewhere does not enter into it.
      "Dr. Juan Q. Xavier de la Vega III"  →  family_base="Vega"
      "Dr. Juan Q. Xavier de la Vega III"  →  family_particles="de la"
      "Anh Do"                    →  family_base="Do"
      "Juan van der"              →  family_base="van der"
      "Juan van der"              →  family_particles=""
      "Juan de la Vega"           →  family_base="Vega"  · boundary
      "Juan de la Vega"           →  family_particles="de la"
      "Sean O'Connor"             →  family_base="O'Connor"
    Accepted, and the invariant it exists to hold: a non-empty
    family always has a non-empty base. A particle needs a base to
    attach to, so a family that is all particles is a family whose
    words are not acting as particles.
      "Del Toro"  family-first    →  family_base="Del"
    Accepted: the test runs after every rule that moves a token
    between parts, so O3's fold decides it too — a middle folded into
    the family can leave the family all particles, or can give a
    trailing particle the name word it was missing.
      "Anh Van Do"  middle_as_family  →  family_base="Van Do"
      "Nguyen, Van Le"  middle_as_family  →  family_particles="Le"
    history: decisions.md#R2 · interacts: R3 · implemented: nameparser/_types.py, nameparser/_pipeline/_post_rules.py, nameparser/_facade.py

R3. Rationale: initials abbreviate the person's name words; titles,
    suffixes, particles and nicknames are not name words.
    Initials take the first letter of each given, middle, and base
    family word; titles, suffixes, particles and nicknames
    contribute nothing — except the particles of a part whose every
    word is one, which are not acting as particles there (R2) and
    initial like any other name word. A CONJUNCTION never initials,
    so a base that is one contributes nothing even then.
      "Dr. Juan Q. Xavier de la Vega III"  →  initials="J. Q. X. V."
      "Anh Do"                    →  initials="A. D."
      "Nguyen, Van Le"            →  initials="V. L. N."
      "Sean O'Connor"             →  initials="S. O."  · boundary
    A family that is ALL particles therefore contributes its words
    rather than nothing: they are the base (R2), so they initial.
      "Juan van der"              →  initials="J. v. d."
      "Juan de y"                 →  initials="J."
    history: decisions.md#R2 · interacts: R2 · implemented: nameparser/_render.py, nameparser/_facade.py

R4. Rationale: case repair is a display concern, applied only on
    request and never destructively.
    Case repair returns a repaired copy — vocabulary exceptions
    (McDonald) included — and never mutates the parse; an
    already-correct name comes back unchanged.
      "juan mcdonald"             →  capitalized="Juan McDonald"
      "Juan McDonald"             →  capitalized="Juan McDonald"  · boundary
    implemented: nameparser/_render.py

## Construction & configuration diagnostics (D)

Background: configuration mistakes are reported when they are made — at construction — not when a name happens to hit them; and a diagnostic that hands the reader code must hand code that works and type-checks.

D1. Rationale: a parser whose activated scripts nothing can divide
    behaves like a working parser minus a feature, silently — the
    one misconfiguration a caller cannot see in output.
    Constructing a parser that activates division for scripts with
    no covering surnames and no segmenter warns at construction,
    naming the dead scripts and each way out.
      [segmenterless-ja]  →  warns="deactivate with Policy(segment_scripts=frozenset())"
    no-boundary: any covering surname vocabulary, configured
    segmenter, or deactivation silences it — the default parser and
    the zh pack never warn, which every other example in this
    document exercises.
    history: decisions.md#D1 · implemented: nameparser/_parser.py

D2. Rationale: whatever a name contains, parsing answers; only a
    broken configuration may raise, and it must name the field.
    Configuration validation raises at construction with the
    offending field and value named; applying a locale pack wraps
    any such error with the locale's code, so a stacked
    configuration names which layer broke.
      [bad-name-order]  →  raises="name_order elements must be Role members"
      [bad-order-none]  →  raises="name_order must be an iterable"
    no-boundary: the non-raising side is every other rule's
    examples; parse() itself is total (A1).
    history: decisions.md#D2 · implemented: nameparser/_policy.py, nameparser/_parser.py
