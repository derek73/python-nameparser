# Parsing rules

This document is NORMATIVE, not descriptive: the rules state how names are written and what should happen when they are parsed, grounded in how people understand names — not in what the parser currently does. The parser implements these rules. Where it does not yet, the gap is a tracked deviation (`deviates:` marker below), not a counterexample. Statements are implementation-free: no stage names, no function names, no regexes.

Authority, scoped: `tests/v2/cases.py` pins CURRENT behavior; this document states INTENDED behavior. A mismatch between them must be classified, never defaulted: either the rule is wrong (fix it here) or the parser is wrong (the example takes a `deviates:` marker and an issue). Where this document is silent, the behavior is pinned-but-undocumented — an extraction gap to close, not a specification, and not license to change the behavior.

Rule IDs are stable forever: never renumbered, never reused. A retired rule keeps its ID with a one-line tombstone pointing at decisions.md. Cross-references use the anchor form `decisions.md#P2` / `mechanisms.md#SPANS`; a bare ID is never a citation. The `interacts:` field on a pointer line is advisory — the citation-integrity test checks the ID exists, not that the interaction is real. `implemented:` and `tracked:` are not advisory: every rule carries exactly one. `implemented:` names the modules honoring the rule, checked against the modules that cite it; `tracked:` names the issues that would ship a rule nothing implements yet, so a wholly-aspirational rule cannot sit here untracked, and a shipped rule cannot keep a stale tracking pointer.

Every example line is EXECUTABLE. The grammar (its executable definition is `tests/v2/rules_doc.py`; `tests/v2/test_rules_doc.py` runs every line):

    "INPUT" [annotation] →  field="value"  [· boundary]
                            [deviates: #N (today: field="value")]

An `annotation` names a policy, locale (`[ru]`), or extras gate (`[ja+segmenter]`) in the registry beside the test. `· boundary` marks the non-firing example every rule must carry: an input shaped like the rule's subject where its effect does NOT occur. That is usually the rule's OWN stated exception — H1's given-name title, P3's single-letter carve-out — not an input the rule never reaches, so the exception is executable rather than merely asserted. Or the rule declares `no-boundary: <reason>` instead, so skipping the boundary is a recorded decision. `deviates:` states the INTENDED output on the example line while the marker records TODAY's output and the tracking issue; the runner asserts today's output strictly, so a parser change that closes the gap fails the suite until the marker is removed in the same PR. `grep deviates:` on this file is the deviation backlog (deviations from statable rules — coverage gaps are a separate, larger category no grep can see, and contested vocabulary memberships a third, tracked as Open blocks keyed to the vocabulary set in decisions.md).

One class of rule stands outside the normative reading and declares it on a `tolerated: <reason>` line beside its pointer line. Such a rule is ABOUT an input the writing systems it speaks about do not produce — a shape no convention writes, read best-effort because parsing is total over strings — and it describes what the parser does with that input instead of promising it. Its statement is still precedence-bearing and its examples are still executable and still run, but they illustrate rather than promise, and the behavior is changeable without notice. W3 is the only such rule today (the 2026-09-01 comma demotion).

The marker's unit is the whole rule, because that is the unit `tools/differential/build_rules_corpus.py` skips: it harvests no example from a marked rule, so none of them is enforced against released baselines. Two obligations follow, and neither is automatic. A clause that reaches past the tolerated shape does not belong in a marked rule — say it in a normative one. And the skip only STOPS enforcing a name; keeping it watched is a separate act, discharged here by giving each demoted example a `tolerated` row in `tests/v2/cases.py`, which projects it onto the differential's radar tier.

## Not in scope

- **Language detection.** The parser never infers a language from Latin-script text: transliteration destroys the signal ("Ali",
  "Van", "Bin" each belong to several languages with conflicting
  readings). Language-specific behavior is opt-in configuration. Script-conditional behavior exists only where the script itself settles the convention (see the W section).
- **Grammatical inflection.** Names inflect in many languages (vocative, genitive); this library neither produces nor consumes inflected forms. CLDR personNames draws the same line.
- **Validation.** Deciding whether a string IS a person's name is not parsing; `parse()` is total over strings and never rejects input.
- **Vocabulary completeness.** No shipped wordlist parses every name, and none is meant to. The promise is that every TYPE of vocabulary has a mechanism — markers, particles, titles, suffixes, bound given names — and that callers configure the members their data needs. A missing entry is a configuration answer, not a defect, and what the tests owe is one exercise per behavioral fork rather than one per entry (mechanisms.md#VOCABULARY-EXERCISES-FORKS).
- **Comparison.** matches()/comparison_key() are a value-API surface, not parsing; their design record is decisions.md#comparison-surface.

## Titles & honorifics (H)

Background: an honorific title precedes a name and is not itself part of it; it addresses or ranks the person. Most titles address by surname ("Mr. Johnson"), but a few — knighthoods, some clerical and courtesy titles — address by given name ("Sir John"). The library keeps a vocabulary of titles and, separately, of these given-name titles. A period-marked word is claimed by SHAPE at the front and by VOCABULARY at the back. At the front an unlisted abbreviation is a title (H2), the shape outranking the vocabulary; at the back there is no shape rule, so only a listed title word chains into the title (H5) and an unlisted abbreviation stays a name word. A BARE title word at the back is a name word too, TITLES holding ordinary surnames — king, judge, bishop — which is what bars the blanket vocabulary-wins answer (#316, decided 2026-09-08). An input the title peel eats down to one last title-vocabulary word is H4's, and what it does with that word is a convention rather than a reading of the vocabulary. Two criteria govern two different questions here. Membership in the given-name-title list follows HOW THE TITLE ADDRESSES: a title that precedes and addresses by the given name belongs (Sir, Sheikh, the Arabic honorifics الدكتور/الشيخ — which qualify even though those traditions fully retain family names). Whether an EMPTY FAMILY is correct output is the separate question, governed by surname retention: renunciation abolishes the surname, so for Swami, Guru, Baba or Lama family="" is right (#346), while rabbi and imam traditions keep surnames — "Rabbi Cohen" addresses by title and keeps family "Cohen". Conflating the two criteria either ejects the Arabic entries or sweeps in titles that break
"Rabbi Cohen".

H1. Rationale: a title normally addresses by surname, so a title
    followed by a single name word usually names the family; but a
    given-name title addresses by given name. Several titles written
    together are one form of address, and the one that does the
    addressing is the last — the words in front of it rank the
    person rather than name them. What stands beside the name word —
    a suffix, a nickname, a maiden name — does not make the name any
    longer, so it does not decide this reading. And a run written
    BEHIND the one name word is the same form of address written on
    the other side of it, so where no title run stands in front of
    that word it decides the same reading. Where one does stand in
    front, that run addresses: a title written behind the name is
    the name plus that title (H5), and adding it cannot change how
    the words in front of the name are read. Which side a title is
    on is decided by the NAME WORD and by nothing else standing
    beside it, so a run written around a nickname is one run: the
    name Dr. 'Smitty' Sir John reads as Dr. Sir John does.
    A title followed by exactly one name word makes that word the
    family name, whatever suffix, nickname or maiden name stands
    beside it, unless the title is a given-name title, which keeps
    it the given name; a run of several titles addresses as its last
    title does, and where a run stands BEFORE the one name word it
    is the run that addresses, a run standing behind it deciding
    that word's field only when none stands before.
      "Mr. Johnson"               →  family="Johnson"
      "Mrs. Garcia"               →  family="Garcia"
      "Dr. Smith née Jones"       →  family="Smith"
      "Her Majesty Queen Elizabeth"  →  given="Elizabeth"
      "Dr. Sir John"              →  given="John"
      "Smith Sir."                →  given="Smith"
      "Sir John Prof."            →  given="John"
      "Dr. Smith Sir."            →  family="Smith"
      "His Excellency Lord Duncan"  →  family="Duncan"
      "Her Royal Highness Princess Anne"  →  given="Anne"
      "Sir John"                  →  given="John"  · boundary
    Accepted: a given-name title plus one name word leaves the
    family empty — the input names no family, and inventing one
    would be worse. A run whose last title is a given-name title
    reads the same way, `queen` doing the addressing where `her
    majesty` only ranks.
      "Sir John"                  →  family=""
      "Her Majesty Queen Elizabeth"  →  family=""
      "Smith Sir."                →  family=""
    Accepted: a title word in the run that no vocabulary knows does
    not change what the run addresses by, the last word being the
    one asked — `His Excellency Lord Duncan` reads family `Duncan`
    because `lord` is not a given-name title, not because the run is
    long. `lord` and `lady` stay out of that list by decision
    (#519): each addresses by given name only as a courtesy style for
    children of the senior ranks (`Lord Peter`, `Lady Diana`) and by
    title or surname for every peer and every wife (`Lord Byron`,
    `Lady Thatcher`), and the text does not say which the bearer is,
    which the list cannot express; `prince` and `princess` are in it.
    history: decisions.md#H1 · interacts: H3, H5, P2, P3, P5, M2, S1, S2, N1, N3 · implemented: nameparser/_pipeline/_post_rules.py

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
    word, and only vocabulary can recognize it — which is what #343
    and #344 supply for Bengali and Devanagari.
      "প্রকৌশলী. Sen"             →  given="প্রকৌশলী."
    Accepted: the shape reads a Latin convention, and a script with
    no initials has no period abbreviations either, so a period-
    marked opening word carrying a Han, kana or hangul character —
    as the script table classifies them; halfwidth katakana sits
    outside it and still reads by the Latin shape, the limit
    decisions.md#cjk-full-stops records — is a name word and never a
    title by shape (#323; decisions.md#cjk-full-stops) — the same
    veto that keeps 씨. from reading as an initial. The Latin
    reading is unchanged, and W3's example block carries the CJK
    reading this clause vetoes into.
      "Smith. John"               →  title="Smith."
    Accepted: before a family comma the pre-comma text is wholly the
    family name (C1), so no shape or vocabulary reading makes a
    title there.
      "Xyz. Smith, John"          →  family="Xyz. Smith"
    Accepted: after a family comma a part that is nothing but suffix
    words is the credential run (C1), which the abbreviation does
    not open: the vocabulary decides, and "Esq." is the postnominal
    it is.
      "Smith, Esq."               →  suffix="Esq."
    history: decisions.md#H2 · interacts: C1, P4, H5, W3, W4 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py

H3. Rationale: compound titles are written as a run of title words,
    connectives included; a title word standing inside the name is
    just a name word. And a title addresses somebody, so the run
    leaves somebody there to address: a post-nominal is written
    about a name rather than being one, so it cannot be the name the
    run left.
    Successive title words at the start of the part carrying the
    given name chain into one title; a title word elsewhere in the
    name does not. The run leaves one NAME word standing, and a word
    of the suffix vocabulary is not that word — where everything
    behind the run is post-nominal, the run gives its last word back
    to the name, provided that word stands alone and is not itself
    suffix vocabulary.
      "Asst. Vice Chancellor John Smith"  →  title="Asst. Vice Chancellor"
      "Marquess of Bath"          →  title="Marquess of Bath"
      "Morse, Det. Insp. Jane"    →  title="Det. Insp."
      "Dr King Jr"                →  family="King"
      "Dr King Jr"                →  suffix="Jr"
      "MD DDS"                    →  family="DDS"
      "John Doctor Smith"         →  middle="Doctor"  · boundary
    Accepted: before a family comma the pre-comma text is wholly the
    family name (C1), title words included.
      "Dr. Smith, John"           →  family="Dr. Smith"
    Accepted: the word given back must stand alone, so a title
    written as one joined unit stays whole and the post-nominal
    behind it is the name — turning the unit into a name and leaving
    no title at all is the worse of the two readings.
      "Prince of Wales Jr"        →  title="Prince of Wales"
    Accepted: where the run's whole content is the word given back,
    no title is left to make the reading H1's, so the word stands as
    the name and the parse reports the doubt (H4).
      "Dr Jr"                     →  given="Dr"
      "Dr Jr"                     →  ambiguities=("title-or-name",)
    history: decisions.md#H3 · interacts: C1, H1, H4, H5, S2 · implemented: nameparser/_pipeline/_pieces.py

H4. Rationale: this is a name parser, not a title parser. Handed a
    string the title peel eats down to one last word which is itself
    title vocabulary, it still has to name somebody, and that word is
    the only candidate there is — a guess fixed in advance, so the
    same input reads the same way every time, not a claim that the
    word is a surname. The same reasoning covers a string that is
    nothing but post-nominal vocabulary: something has to be the name.
    An input whose only remaining name word after the title peel is
    itself title vocabulary reads that word as the name by convention
    and reports `title-or-name`; an input whose every word is
    post-nominal vocabulary reads its first word as a name and
    reports `suffix-or-name`. A single title word reads as a title
    with no name beside it and reports nothing: the peel took the
    whole string, so no word was left standing to be read as a name
    and no reading was chosen.
      "Lord Chancellor"           →  family="Chancellor"
      "Lord Chancellor"           →  ambiguities=("title-or-name",)
      "The Right Hon. the President of the Queen's Bench Division"  →  family="Division"
      "The Right Hon. the President of the Queen's Bench Division"  →  ambiguities=("title-or-name",)
      "Dr. King"                  →  ambiguities=("title-or-name",)
      "Dr. King MD"               →  ambiguities=("title-or-name",)
      "Dr."                       →  title="Dr."  · boundary
      "Dr."                       →  ambiguities=()
      "Dr. Smith"                 →  ambiguities=()
    Accepted: ONE site takes both halves — the assignment that places
    the lone name word — so neither report depends on the declared
    order. Under the default order H1 retags the title-vocabulary
    word from given to family afterwards; under a declared
    family-first order the assignment places it in the family
    directly and H1 never runs. Same reading either way, so the same
    kind is reported either way.
    Accepted: the suffix half is reached only where no title was
    peeled first, so a title in front of the run takes the input out
    of that half. What it does NOT do is take the input out of the
    rule: the title run leaves a name word standing (H3), and where
    that word is title vocabulary the TITLE half claims it —
    `Dr. King MD` reports `title-or-name` on `King`, while `MD DDS`
    reports nothing, `DDS` being no title.
      "MD DDS"                    →  ambiguities=()
      "Rinpoche"                  →  ambiguities=("suffix-or-name",)
      "QC MP"                     →  given="QC"
      "Jr."                       →  title="Jr."
      "Jr."                       →  ambiguities=()
    Accepted: `Jr.` is post-nominal vocabulary and still reads as a
    title, H2's opening-abbreviation shape outranking the vocabulary
    where it fires — so the suffix half never sees a dotted lone
    credential.
    Accepted: the suffix half is scoped to names no script order
    placed, so a lone CJK honorific written by itself — さん, 씨,
    선생님 — reports nothing. The same shape, read through the
    glued-honorific rules (W2) and the script's own order, and left
    to the arc that revisits those readings. That silence is a SCOPE
    on the script rule having placed the name, not a claim about the
    honorific: a caller who declares no script orders at all gets the
    report on the same input, since nothing then resolves the order
    and the word reaches the carve-out as any other lone credential
    does. The pair is pinned in the case table rather than here,
    a policy that empties the script table having no example spelling
    in this document.
    Accepted: one name UNIT of more than one word carrying title
    vocabulary reports `title-or-name` as well, the fork there being
    whether the title word inside the unit is a title at all. Usually
    a join (P3), and a particle chain (P4) is the same shape and
    reports too — `St St née` reads family "St née" with `st` title
    vocabulary inside it. The
    clause reaches EVERY join whose non-leading member is TITLES
    vocabulary, not the one word that prompted it: `Smith and King`,
    `John and King`, `Smith and Bishop` and `John of Judge` all
    report it, as `John of Prince` and `Smith and Prince` do. That
    reach is the king/judge/bishop collision set met inside a join,
    and the report is the honest answer there rather than a
    misfire — a second surname that is also title vocabulary is
    exactly the doubt the kind names, and those words stay in the
    vocabulary for the addressing forms, which is
    decisions.md#vocabulary-collisions' call.
    A join OPENING the name with a title word is a title run (H3)
    instead. Behind a peeled title the join is not: a title needs a
    following piece and the join is the last one, so `Attorney General
    of Minnesota` and `Deputy Secretary of State` keep `Attorney` and
    `Deputy` as the title and report the rest — the two corpus names
    the clause reaches, and `General` or `Secretary` being a title is
    exactly the fork. Nothing in front of the join silences the
    clause, a title, a maiden name or a claimed word each deciding
    which FIELD the unit takes and none of them whether the word
    inside it is a title. The other measured inputs are pinned in the
    case table rather than here.
    history: decisions.md#H4 · interacts: H1, H2, H3, H5, S2, O5 · implemented: nameparser/_pipeline/_assign.py

H5. Rationale: a word abbreviated with a period at the END of a name
    is standing where a post-nominal stands, and the parts of a name
    that get abbreviated are the ones outside it. There is no shape
    rule there — H2's belongs to the front slot — so only a word the
    vocabulary knows as a title is one, and a bare title word is a
    name word, TITLES holding ordinary surnames.
    After the trailing suffix run has been taken, successive single
    words that wear the abbreviation shape and are title vocabulary
    chain into the title from the end, leaving one name word
    standing. A bare title word there is a name word, and an
    unlisted abbreviation there is a name word. The title is
    TRANSPARENT to the suffix reading: where two or more name words
    stand, what stands once the chain is taken reads exactly as it
    would read written without the title, plus the title. Where the
    chain leaves ONE name word and no title run stands in front of
    it, there is no second reading for it to be transparent to, and
    the title behind that word decides its field as a title in front
    of it would (H1). Where a run DOES stand in front, that run
    addresses and the chained title only joins the title field, so
    the transparency holds for the one-word name too.
      "John Smith Prof."          →  title="Prof."
      "John Smith Prof."          →  family="Smith"
      "John Smith Prof. Dr."      →  title="Prof. Dr."
      "Dr. John Smith Prof."      →  title="Dr. Prof."
      "Smith, John Prof."         →  title="Prof."
      "Smith Prof."               →  family="Smith"
      "John Smith Sir"            →  family="Sir"
      "Mary Jane King"            →  family="King"
      "John Smith Esq."           →  suffix="Esq."
      "John Smith Xyz."           →  family="Xyz."  · boundary
    Accepted: the trailing title words join the title field in input
    order after any leading run, because the title view reads the
    tokens in the order they were written.
      "Dr. John Smith Prof."      →  family="Smith"
    Accepted: transparency is what makes the suffix reading proof
    against a title standing among the post-nominals — a title AHEAD
    of a suffix word is taken all the same, and the suffix reading
    is then taken over what stands, not over what stood.
      "John Smith Prof. Jr."      →  suffix="Jr."
      "John Smith Jr. Prof."      →  suffix="Jr."
      "John Prof. MA"             →  suffix="MA"
      "JOHN PROF. MA"             →  family="MA"
    Accepted: the reach is the whole title vocabulary, the ordinary
    surnames in it included. TITLES holds king, judge and bishop,
    and a period written behind one of them is enough to make it the
    title and take it out of the name: `Mary Jane King.` reads title
    `King.` with family `Jane`, where the bare spelling keeps family
    `King`. That is a cost accepted under the premise that the input
    is a name (H Background), not a case this rule prevents — the
    period is a writing convention rather than evidence about the
    word, so every title whose spelling wears the abbreviation shape
    is reachable this way, and the BARE spelling is what the
    trailing slot is protected from.
      "Mary Jane King."           →  title="King."
      "Mary Jane King."           →  family="Jane"
    Accepted: no fork is reported. Under the premise that the input
    is a name, a period-marked word the title vocabulary knows is
    not a reading a reader would hesitate over — where the doubt is
    real it is the word left STANDING that carries it, which is H4's
    report and not this rule's.
    Accepted: the chain reads PIECES, so a join that ran earlier
    puts the word out of reach. A particle chain (P2) has already
    taken the trailing word into the family name, and a maiden
    marker (M2) has already taken it into the maiden name; in
    neither is a title word standing in the trailing slot at all.
      "John van der Berg Prof."   →  family="van der Berg Prof."
      "Mary Smith née Jones Prof." →  maiden="Jones Prof."
    Accepted: what the chain leaves is also what counts as a name
    word to spare (P5). A trailing title word is not one, so a bound
    given-name word behind one joins exactly as it joins with the
    title absent — and lands in the same field, the run in FRONT of
    the joined pair being the run H1 asks about. Said of the
    comma-less writing, which is where the chain runs before the
    reserve is read. After a family comma the reserve reads no peel
    at all (P5), so the join there takes the trailing title word into
    the given name and the chain never sees it, where the same
    segment writing with an ordinary given name reads the title. A
    gap in the segment path rather than a boundary of this rule, and
    tracked as part of #316. Pinned by a case row rather than by an
    example here, so recording the gap does not make it normative.
    history: decisions.md#H5 · interacts: H1, H2, H3, H4, M2, P2, P5, S2, C1 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py

## Particles & surname prefixes (P)

Background: particles ("de", "la", "van", "von", "bin") link forward to a surname and are written as part of it. Some are never anyone's given name; others ("Van", "Bin") are ordinary given names in some cultures, so the vocabulary distinguishes never-given particles from ambiguous ones, and only the never-given ones license special treatment. A separate small vocabulary binds forward to a GIVEN name instead: words like "abdul" that are not complete given names alone (P5). Which particles fall on which side of the never-given line is its own open question (#360).

P1. Rationale: a particle OPENING a name has the whole rest of the
    name to link forward to, so it is doing a particle's work and the
    piece it heads is a surname written out in full. That is evidence
    about the writing, not about the word, which is why no declared
    order contradicts it.
    A never-given particle opening the name marks the name as
    surname-only: the particle run and the name words it attaches to
    are the family. It needs another name word to attach to. The run
    is every particle in sequence, never-given and ambiguous alike
    ("de la Vega" is one group, not "de" plus a separate "la Vega").
    An ambiguous particle keeps whatever reading its position gives
    it. That the particle claims the FAMILY rather than a given name
    holds under every order: this is evidence about how the name is
    written, and a declared order governs only what no vocabulary has
    claimed (O4) — the same precedence the script license takes in W4.
    The OPENING position is the whole of this rule's subject. A
    particle standing where the given name would go was a second site
    until #467, and dropping it is a correction rather than a
    narrowing: that slot holds what the caller DECLARED to be the
    given name, and the never-given vocabulary supplies a reading
    where position leaves the question open rather than vetoing one
    position has already given. A particle ending the name is P6's,
    and only where it landed in a MIDDLE.

    How MANY name words it attaches to depends on the order. Under a
    family-first order it takes exactly ONE — declaring that order
    asserts that what follows the family is not more surname. Under
    the default order it takes the rest of the name, and that is a
    reading rather than a gap in one: a never-given particle marks
    where a surname BEGINS, surnames are routinely several words,
    and no declaration has said this one ends before the string
    does. So `de Mesnil Jean` reports the whole string as the
    family, which is 1.4.0's reach as well (#471, declined by
    design). One name word means one UNIT — a particle chain (P2),
    a conjunction join (P3) or a bound given-name pair (P5) is
    taken whole or not at all. A title does not move the opening
    position (P4), but a family comma does end the question: the
    comma has already fixed the surname, so there is no positional
    read left for an order to narrow, and a particle opening the
    part AFTER it takes the rest of that part whatever order is
    declared. What is left over is not read by O4's rule for a
    whole name, which would make the first leftover a second family
    name; it is laid out as the positions AFTER the family in the
    declared order, the family slot being already filled.
      "de la Vega"                →  family="de la Vega"
      "Sir de Mesnil"             →  family="de Mesnil"
      "Mesnil de"  family-first   →  given="de"
      "de Mesnil Jean"            →  family="de Mesnil Jean"
      "de Mesnil Jean"  family-first  →  family="de Mesnil"
      "de Mesnil Jean"  family-first  →  given="Jean"
      "Smith, de Mesnil Jean"  family-first  →  family="Smith de Mesnil Jean"
      "de la Vega y Santos Juan"  family-first  →  family="de la Vega y Santos"
      "ibn Awf abdul Rahman"  family-first  →  given="abdul Rahman"
      "de la Cruz Juan Carlos"  family-first-given-last  →  given="Carlos"
      "Mc Donald"                 →  family="Mc Donald"
      "de los Santos"             →  family="de los Santos"
      "van Gogh"                  →  given="van"  · boundary
    Accepted: the default-order reach has two faces, and the second
    is a real cost. A surname-only string is read right, which is
    what the reach is for; a family-first listing read under the
    default order is read wrong, all of it landing in the family.
    The remedy is the declaration or the comma — declare a
    family-first order, which gives family `de la Cruz`, given
    `Juan`, middle `Carlos`, or write the family comma. What
    NEITHER order settles is the comma's alone: `de la Family
    Family Given` and `de la Family Given Given` are the same
    string shape, and no reading of the words tells them apart.
      "de la Torre Vega"          →  family="de la Torre Vega"
      "de la Cruz Juan Carlos"    →  family="de la Cruz Juan Carlos"
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
    does, and so does a bare ambiguous acronym written in capitals in
    a mixed-case name, which needs no words to spare; the same
    acronym written Title-case in a mixed-case name ends nothing and
    joins the chain as any name word does, words to spare or not,
    and the fork the chain called is reported there exactly as it is
    where no particle stands (S2) —
    a maiden
    marker takes the
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
      "John van der Berg Ma"      →  family="van der Berg Ma"
      "John van der Berg Ma"      →  ambiguities=("suffix-or-name",)
      "john van der berg ma"      →  suffix="ma"
      "John van der J. V"         →  family="van der J. V"  · boundary
      "Freiherr von Berg MA"      →  family="von Berg"
      "Freiherr von Berg MA"      →  suffix="MA"
      "Freiherr von Richthofen V" →  suffix="V"  · boundary
      "John van der Berg née Jones"  →  family="van der Berg"
    Accepted: a particle of the unambiguous suffix vocabulary too
    (vd, mc) is a suffix piece to the peel, so where it opens the
    trailing run the chain stops before it as before any suffix
    word, and the peel takes it; where it continues a prefix run,
    the run takes it as a particle, as P6 reads it after a comma —
    and there the chain reports nothing, the particle reading being
    P6's fork rather than S2's.
    The same carve-out covers `do`, the one word that is both a
    particle and an AMBIGUOUS credential acronym: where a particle
    run takes it, the word is the run's and the chain reports
    nothing, whatever case it is written in — so `Anh van Do` is
    silent where `Anh Do`, with no particle standing, reports.
    A word that is both belongs to the particle run and to P6's
    fork, not to S2's.
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
    history: decisions.md#P2 · interacts: P1, P4, H5, M2, S2 · implemented: nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py

P3. Rationale: connective words ("y", "of the") bind name words into
    one name part; but a single letter in a short name is more
    likely an initial than a connective, and where a name is written
    in more than one case, a bare Latin capital standing alone is how
    an initial is marked and a bare lowercase letter is how it is
    not.
    A recognized connective joins its neighbors into one name part,
    connective runs included — except a single-letter connective in
    a three-word name, which stays a name word, and a single-letter
    connective that reads as an initial instead, which never joins.
    A single-letter connective reads as an initial where the writing
    says so: written as a bare Latin capital in a name that is not written
    wholly in one case, or — in a name written wholly in one case,
    where nothing says so — where the letter is one the vocabulary
    marks as reading both ways.
    A letter the vocabulary marks as reading both ways, read as an
    initial in a name written wholly in one case, is a call that could
    have gone the other way, and is reported.
    The joined part is ONE name word wherever another rule counts
    them, so a rule taking "one name word" takes the whole join and
    never half of it.
    Both questions this rule asks of a name — how many words it has,
    and whether it is written in one case — are asked of the name's
    OWN words: a maiden marker taken as one, and the words it takes
    (M2), are not among them, and neither is a delimited clause (N1,
    M1). So a clause beside the name changes neither whether the
    connective joins nor how a letter in the name reads, and a letter
    inside such a clause is the clause's word, read as it always was
    and not by this rule. The two questions part at one point: a
    marker the pass declines and leaves as a word (M2) is a word, and
    counts toward the three — but its case is still not asked.
    That span is not this rule's alone: wherever another rule asks
    the case question — the suffix slot (S2) and the post-comma slot
    (C1) — it is asked of these same words, so the answer is taken
    once and read where each of them stands.
      "Juan y Eva Garcia"         →  given="Juan y Eva"
      "Jose E Maria Santos"       →  middle="E Maria"
      "jose e maria santos"       →  middle="e maria"
      "Jose e Maria Santos"       →  given="Jose e Maria"
      "JUAN GARCIA Y LOPEZ"       →  family="GARCIA Y LOPEZ"
      "juan garcia y lopez"       →  family="garcia y lopez"
      "john e smith"              →  middle="e"
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
    e. The initial reading counts letters too, and asks one more
    question of them: a letter with no case at all (و) can be written
    against nothing, so it never reads as an initial. A Cyrillic
    capital has case but is not the shape an initial is written in —
    Cyrillic abbreviates with a dotted letter — so in a name of more
    than one case it joins, the reading #267 blessed, and in a name
    of one case it takes the vocabulary's answer like any other cased
    letter.
    Which single letters a tradition actually wants joined differs by
    language, and the marked set is where that answer lives: "y" is
    the commonest Hispanic compound and stays out of it, "e" is a
    common bare initial and is the one entry shipped. A caller with
    Portuguese data removes it; a caller with Dutch data adds "y".
    The initial reading is visible beyond the fields, on the two
    derived views: parse("john e smith").initials() gives "j. e. s."
    and .capitalized() gives "John E Smith", where the connective
    reading gave "j. s." and "John e Smith" — a connective
    contributing no initial (R3) and keeping its lowercase (R4),
    where an initial does neither. The v1 facade's initials() still
    reads the letter by vocabulary and written shape rather than by
    the parse's reading, so HumanName("john e smith").initials()
    stays "j. s." for now; decisions.md#P3 records the split.
    Accepted: two 1.4.0 parity breaks, one in each direction. A bare
    capital in a name written wholly in upper case no longer reads as
    an initial, so "JUAN GARCIA Y LOPEZ" joins where 1.4.0 and
    2.0–2.3 read middle "GARCIA Y"; and a marked lowercase letter in
    a name written wholly in lower case no longer joins, so "jose e
    maria santos" reads middle "e maria" where they read given "jose
    e maria". That is #383 answered with "bless" for the mixed-case
    half — a bare Latin capital among mixed case still reads as an
    initial, the shape the veto always tested, which is why #267's
    Cyrillic reading is untouched — and answered with evidence for
    the one-case half, where the vocabulary decides.
    A maiden marker's run and every word after it are outside the
    name's own words from the moment classify tags the marker, and
    they stay outside whether or not the marker pass later declines
    the marker and leaves it a word (M2). A declined marker therefore
    does two things at once. It still does not count toward the case
    class, which shows when it is the only differently-cased token,
    so "JUAN Y GARCIA née" joins where "JUAN Y GARCIA née Jones"
    keeps "Y" a name word. And it leaves any connective standing
    after it to the mixed-case rule rather than to the one-case fork,
    so a bare Latin capital there reads as an initial while its
    lowercase spelling joins — the one shape in which the name's OWN
    words read differently in its two one-case spellings. So "JUAN
    NÉE JR Y LOPEZ" reads middle "NÉE JR Y" with its "Y" an initial,
    while "juan née jr y lopez" reads family "jr y lopez" with its
    own "y" joined. A clause's words are read as they always were,
    and that is not an exception to this: such a letter still takes
    a different tag in the two spellings, so its case repair can
    differ between them, which is a repair difference and not a
    reading of the name's own words.
    Accepted rather than repaired: classify cannot know what group
    will decline, and a clause's words are read by the clause's own
    rules.
      "Хосе И Мария Сантос"       →  given="Хосе И Мария"
    H1 is the counting rule that shows the one-word clause today: a
    title plus the join reads the whole join as the family, where the
    same two words unjoined are two name words and H1 does not fire.
    P1's leading run is the second (#395, landed): its run takes
    the "Vega y Santos" join whole or stops before it.
    history: decisions.md#P3 · interacts: H1, P1, M2, R3, R4 · implemented: nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_post_rules.py

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
    name, nor a suffix word is joined. A run of several titles is
    read as H1 reads it, by the title that does the addressing,
    which is its last. Where the join fires, a bound word that is
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
    leave them, and the same reading assign runs over them — its
    trailing peel (S2) and its trailing title run (H5), each read
    over what the other leaves until neither takes anything more —
    is read over that view, the name words it leaves being the words
    to spare. A trailing
    roman numeral, or a bare acronym the peel takes, or a trailing
    title word the run takes, is no
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
      "abdul Smith Jr Ma"         →  given="abdul Smith"
      "abdul Smith Jr Ma"         →  middle="Jr"
      "abdul Smith Ma"            →  given="abdul Smith"
      "abdul Smith Berg Ma"       →  middle="Berg"  · boundary
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
    history: decisions.md#P5 · interacts: S2, M2, H1, H5, P2, P4, P6 · implemented: nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py

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
    often than the decoration it collides with. One exception, and it
    is where the capitals speak: a word of the AMBIGUOUS credential
    class, written in capitals in a name written in more than one
    case, reads as the credential and this attachment stands down —
    unless a particle stands immediately in front of it, the two
    being one particle run by then, which this rule takes whole.
    Every other spelling of such a word attaches as it did before,
    and the kind rule below gives it this rule's particle fork rather
    than S2's credential one. In a name written wholly in one case
    the two readings cannot be told apart and the particle keeps it,
    which is right about a Portuguese record and wrong about a
    credential; the report is how a caller finds the second.
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
    history: decisions.md#P6 · interacts: A1, C1, P1, S2, P5, M2 · implemented: nameparser/_pipeline/_post_rules.py

## Suffixes: generational & credentials (S)

Background: what follows a name is one of two different things — generational suffixes (Jr., III), which attach to the name itself, and credentials (PhD, MD, MBA), which are earned attachments. The suffix sets match one written word at a time: a multi-word entry there can never match anything and is warned about at configuration. Only two sets are exempt from that rule -- given_name_titles and, since #434, maiden_markers -- and neither is a suffix set, so within the suffix vocabulary the one-word rule is absolute. That limit is on STORAGE, not on the shape a name may have: adjacent suffix tokens are reassembled after matching (`_vocab.is_wholly_suffix`), so a multi-word credential is reachable as its component words -- `John Smith, MD PhD` has read suffix `MD PhD` since 1.4.0 -- and a caller reaches an unshipped one by adding the words it is made of rather than the phrase (#433). The eight multi-word entries that shipped dead for years span the suffix sets and the titles alike and are the Excluded story in decisions.md. CLDR personNames keeps them as separate fields (`generation`, `credentials`) and formats them differently; this library currently reports both in one `suffix` field, a merge #326 examines. The vocabulary is largely split already: a generational word list and a credential acronym list, plus a short list of acronyms that are also ordinary names (MA, BA) and so are AMBIGUOUS as bare words.

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
    A suffix never OPENS THE STRING: position outranks the
    vocabulary match, so a suffix-shaped word written before anything
    else reads as whatever its position and shape make it — a title
    where it wears the abbreviation shape (H2), an ordinary name word
    otherwise — and never as a credential belonging to a name that
    has not been written yet. The string, not the name: a title, a
    nickname or a bracketed clause standing first leaves the
    credential reading intact, which is the ONE place this document
    says "opening" and does not mean what P4 and the H Background
    mean by it. A family comma is the other boundary: the comma has
    already named the family, so a credential run may open the part
    after it (C1), and the part before it is that family.
    A trailing word of the suffix vocabulary reads as a suffix —
    generational forms and credential acronyms alike, and an
    ambiguous acronym written with its periods, one after each
    letter, counts unambiguously; a single trailing period is the
    abbreviation shape any word can wear and does not. A
    BARE ambiguous acronym is consumed only when the name has words
    to spare — as the second of two words it stays the family
    name — and at the slots that report, either reading carries the
    ambiguity flag. Those slots are the trailing slot of a name, the
    first slot after a family comma, the trailing slot of the GIVEN
    part after that comma, the trailing slot of a maiden marker's
    clause (M2), and the segments beyond it. A word this document
    says is READ at one of those slots is not always a word one of
    them reports: where a reading moves a word out of the slot that
    asked about it, what reports is the slot it lands in, and that
    may be none — M2 states the case where a clause does it.
    After a family comma, a word of this class ending the GIVEN part
    is read as the comma-less spelling reads a word ending the name,
    and the count is not what decides it there. The comma has already
    named the family and the first name word after it is the given
    name, so the words to spare are there by construction and the
    count says nothing: a word that ENDS that part reads as the
    credential unless its WRITING says otherwise, and a word that
    does not end it is never asked. "Ending the given part" reaches
    past the credentials behind it and past a trailing title, which
    is transparent to this reading as it is to the rest of S2's (H5);
    a name word behind the word ends the reach, and so does a
    PARTICLE the suffix vocabulary does not also claim: it belongs to
    the family the comma already named and is taken there by a rule
    that runs after this reading is made (P6), so `Doe, John MA do`
    keeps its middle name though the capitals would otherwise have
    taken the word. A particle the suffix vocabulary DOES claim is
    looked past like any other credential, so `Doe, John MA vd`
    reads suffix `MA`, with `vd` attaching behind it. Where the
    reach ends, the word is an ordinary middle name, read in silence.
    A particle in FRONT of the word takes it out of this slot as
    well, and takes the word behind it too: where what follows the
    particle reads as a name rather than a credential the two are
    one name, so neither word is asked and neither reports —
    `Doe, John van Ma` reads middle `van Ma` and `Doe, John DO Ed`
    middle `DO Ed`, where `Doe, John van MA` reads suffix `MA` and
    `Doe, John DO` alone reads the credential, both reporting.
    Every word this slot does read reports the fork whichever way it
    went, so a run of members all read as credentials reports once
    for each, as the same words do without the comma — while a
    member the writing keeps as a name
    stops the reading there, and whatever stands in front of it is
    name text, asked nothing and reporting nothing. One member of
    this class is particle vocabulary as well, and where it stands
    alone at this slot P6 decides it: the capitals take it as the
    credential and every other spelling attaches to the family,
    reported there as P6's fork rather than as this one. Behind
    another particle it does not stand alone — the two are one
    particle run by then — and the run attaches whatever the capitals
    say (P6).
    Written case is the other evidence, and it speaks only in a name
    written in more than one case: there a member of the ambiguous
    set written in capitals reads as the credential even with no
    words to spare, and one written in any other cased form that is
    not wholly lower reads as the name even with words to spare. A
    name written wholly in one case says nothing about any word in
    it, and the count decides alone; so does a script with no case
    to write in. After a family comma this evidence is SECOND at the
    FIRST slot after it: the count of name words before the comma
    decides there first (C1), and the case is read only where that
    count leaves the word a name. At the trailing slot of the given
    part the comma has already settled the count, so the writing is
    the only evidence there is.
    An unlisted word joins this same ambiguous class by SHAPE where
    the caller asks for it. Two or more period-separated chunks is
    one such shape, admitted by default (S3); an unlisted all-caps
    alphabetic word of two or more letters, standing in a suffix
    position of a mixed-case name and belonging to no wordlist, is
    the other, admitted only under the caller switch the example
    lines below name. That second shape is OFF by default because
    French and Korean records write the SURNAME in capitals, so it
    is a surname as often as it is a credential and only the caller
    knows which corpus this is; the cost of turning it on is that a
    three-word name gives up its family name to the acronym, while a
    two-word name keeps it — there are no words to spare there, so
    the class is considered and declined and only the fork is
    reported.
      "John Smith Jr."            →  suffix="Jr."
      "John Smith M.A."           →  suffix="M.A."
      "John Smith PhD"            →  suffix="PhD"
      "John Ma"                   →  family="Ma"  · boundary
      "Jack MA"                   →  suffix="MA"
      "Jack Ma"                   →  family="Ma"
      "JACK MA"                   →  family="MA"
      "JOHN SMITH MA"             →  suffix="MA"
      "John Smith Ma"             →  family="Ma"
      "Smith, MA"                 →  suffix="MA"
      "Smith, Ma"                 →  given="Ma"
      "Doe, John MA"              →  suffix="MA"
      "Doe, John Ma"              →  middle="Ma"  · boundary
      "Doe, John MA Smith"        →  middle="MA Smith"  · boundary
      "Doe, John DO"              →  suffix="DO"
      "SMITH, JOHN DO"            →  family="DO SMITH"  · boundary
      "Doe, John MA JD"           →  ambiguities=("suffix-or-name", "suffix-or-name")
      "Doe, John MA Ma"           →  middle="MA Ma"  · boundary
      "Doe, John MA Ma"           →  ambiguities=("suffix-or-name",)  · boundary
      "Doe, John van Ma"          →  middle="van Ma"  · boundary
      "Doe, John van Ma"          →  ambiguities=()  · boundary
      "Doe, John DO Ed"           →  middle="DO Ed"  · boundary
      "Doe, John DO Ed"           →  ambiguities=()  · boundary
      "John Smith XYZ"            →  family="XYZ"
      "John Smith XYZ"  unlisted_caps_suffixes-on  →  suffix="XYZ"
      "Jean DUPONT"  unlisted_caps_suffixes-on  →  family="DUPONT"
      "Jean Pierre DUPONT"  unlisted_caps_suffixes-on  →  suffix="DUPONT"
      "Jean Pierre DUPONT"  unlisted_caps_suffixes-on  →  family="Pierre"
      "Jack Ma."                  →  family="Ma."  · boundary
      "Ph. D. Van Johnson"        →  family="Van Johnson"
      "Ph. D. Van Johnson"        →  title="Ph."
      "Smith, Ph. D. Jr."         →  suffix="Ph. D. Jr."
      "II Van Johnson"            →  given="II"  · boundary
      "Sir Ph. D. Van Johnson"    →  suffix="Ph. D."  · boundary
      "Ph. D., John"              →  family="Ph. D."  · boundary
    Accepted: a title before the credential keeps it a credential,
    and the name loses its surname exactly as it did before this
    clause — `Sir Ph. D. Van Johnson` reads given `Van Johnson` with
    an empty family. That is 1.4.0's reading, and the clause cannot
    reach it: the first piece of the NAME is not computable before
    this decision, since the abbreviation test H2 uses is true of
    `Ph.` itself, so a scan that stepped over titles would step over
    the very piece being judged.
    Accepted: an unambiguous suffix is consumed even when that
    leaves no family name at all.
      "Smith Jr."                 →  family=""
    Accepted: the case signal costs a genuine suffix standing behind
    a name-leaning acronym. The walk stops at the declined pick
    rather than continuing past it, so a suffix word in front of one
    is never reached and reads as a name word.
      "Jack Wei Ma"               →  family="Ma"
      "Jack Wei Ma"               →  ambiguities=("suffix-or-name",)
      "abdul Smith Jr Ma"         →  middle="Jr"
    Accepted: the title chain no longer takes the word this rule
    needs, and the argument a descriptive note here asked for is
    made. A title run leaves one NAME word standing and a
    post-nominal cannot be it (H3, decided 2026-09-08), so `Dr King
    Jr` reads family `King`, suffix `Jr` exactly as this rule
    states, where it read title `Dr King`, family `Jr` before —
    `Dr Smith Jr`, which always read as stated, was the contrast
    that isolated the cause and now reads like its neighbour rather
    than against it. What the floor cannot reach stays descriptive
    and is small: where the run's whole content is the word given
    back, no title is left to name anybody, so the word stands as
    the name rather than as the family — `Dr Jr` reads given `Dr`,
    suffix `Jr`, reporting `title-or-name` (H4), and `Sir Jr`, the
    spelling this note first named, reads by the same branches —
    given `Sir`, suffix `Jr`, the same kind reported — the run
    being empty by then and no branch reading `vocab:given-title`.
    The vocabulary half is decided
    and unchanged (decisions.md#v1-xfail-triage: `king` stays a
    title, for the addressing forms).
      "Dr Jr"                     →  suffix="Jr"
    history: decisions.md#S2 · interacts: H1, H2, H3, H5, C1, S3, P2, P5, P6 · implemented: nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py

S3. Rationale: credentials are often written run together with
    periods; the chunks between the periods are what carry the
    vocabulary, and a word of several chunks that no vocabulary
    knows is still written the way a credential is written.
    A word with interior periods reads as a suffix when any of its
    period-separated chunks is suffix vocabulary — except where
    every chunk the vocabulary matches is a single ASCII character,
    the roman numerals and the lone digit the vocabulary lists,
    which are about generations rather than credentials.
    A word of two or more period-separated chunks that no
    vocabulary claims is read by POSITION instead, as a bare
    ambiguous acronym is (S2): a credential where the name has words
    to spare, a name word where it does not, either reading
    reported at the slots S2 reports at, and the same at a comma —
    which means the FIRST piece after a family comma, the word
    trailing the given part after one, the word ending a maiden
    marker's clause (M2), and the part before a SUFFIX
    comma. The part before a FAMILY comma never reports, the comma
    having already named it the family. Case says nothing here — the
    periods are the evidence — and three shapes are outside it: a
    single trailing period is not this shape at all, a chunk that is
    not wholly alphabetic is no acronym letter, and a word carrying
    a script that writes no abbreviations is not wearing an
    abbreviation's periods (H2 refuses the same word for the same
    reason). This second half is a caller switch, ON by default, and
    the example lines name it; turned off, such a word is name
    material and the chunk rule above still decides the rest.
      "John Smith Msc.Ed."        →  suffix="Msc.Ed."
      "John Smith Msc.Ed."  unlisted_dotted_suffixes-off  →  suffix="Msc.Ed."
      "Doe, John Msc.Ed."         →  suffix="Msc.Ed."
      "John Smith J.u.n.i.o.r."   →  suffix="J.u.n.i.o.r."
      "John Smith Q.W.E.R.T."     →  suffix="Q.W.E.R.T."
      "John Smith X.Y.Z."         →  suffix="X.Y.Z."
      "john smith x.y.z."         →  suffix="x.y.z."
      "John Smith X.Y.Z."  unlisted_dotted_suffixes-off  →  family="X.Y.Z."
      "Jack X.Y.I."               →  family="X.Y.I."  · boundary
      "John Smith Xyz."           →  family="Xyz."  · boundary
      "John Smith 1.4"            →  family="1.4"  · boundary
      "Doe, John X.Y.Z."          →  suffix="X.Y.Z."
      "Jane Doe nee Smith X.Y.Z." →  suffix="X.Y.Z."
    Accepted: the initialless-script clause carries no example line
    of its own. Every input that exercises it composes a script that
    writes no abbreviations with a period that only a Latin
    convention writes — `John Smith 田.中.` is the shape — and a
    composed form no writing system produces is tolerated input
    rather than contract. A normative rule cannot hold an example of
    it without putting the string into the corpus that enforces it
    at released baselines, so the witnesses are the tolerated row
    tests/v2/cases.py's
    an_initialless_script_glued_into_periods_is_not_this_shape,
    which keeps the name on the differential's radar tier, and the
    CJK assertions in tests/v2/pipeline/test_vocab.py's
    test_period_joined_vocab_retires_the_single_character_chunk.
    W3 states the same precedence for the same reason.
    history: decisions.md#S2 · interacts: S2, C1, H2, W3 · implemented: nameparser/_pipeline/_vocab.py

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
    Accepted: a marker-led clause is a maiden clause and not a
    nickname one (M3), so this rule does not reach a name written
    that way, and the one name word keeps the reading the bare
    spelling gives it. Since #445 that reading is the family name
    all the same, M4 reaching both spellings from the other side.
    The two rules agree on THIS name and not in general: M4 counts
    name words alone, so where a suffix stands beside them it fires
    and this rule declines. The Accepted line above reads a bare
    nickname-plus-word-plus-suffix name as given with no family, and
    the same name carrying a maiden clause reads family instead.
      "Smith (née Jones)"         →  family="Smith"
    history: decisions.md#N3 · interacts: H1, M3, M4 · implemented: nameparser/_pipeline/_assign.py

## Maiden names (M)

Background: a maiden name is written beside the current name, set off by a marker or by enclosure. Markers are attested across French née/né and the unaccented nee English writing uses for both, German geb./geborene, Dutch geboren, Czech/Slovak rozená (the abbreviation roz. shipped through 2.1 and was removed in 2.2 -- it collides with the English diminutive Roz, and a caller who needs it adds it to their own Lexicon), Scandinavian født/fødd/född, Russian урожд. and its full participles урождённая/урождённый (the participles in both the ё and е spellings, which case normalization does not fold), Japanese 旧姓, and Polish z domu — both grammatical genders where attested. Every one of these is a marker wherever it stands, the unaccented nee included: an enclosure holding a word past it reads as the maiden name and the marker is dropped, so a configured pair reading "(Nee Jones)" gives maiden Jones and not Nee Jones. A marker need not be one word. z domu is two, and a phrase marker is recognized only whole and only where its words stand together: neither of its words is a marker standing alone, and neither is the pair once a bracketed clause or a comma divides them. That is what makes shipping it safe where shipping its words would not be — z is an ordinary Polish preposition, and a name that merely contains one keeps its family name. Japanese more often writes the marker with a fullwidth colon (旧姓：佐藤), which is no separator, so marker and name arrive as a single word. Which enclosures mean "maiden" rather than "nickname" is a caller convention, so the maiden reading of a delimiter pair is opt-in — except where the clause announces itself. A clause of two words or more led by a marker word has said which convention it means, and reads as the maiden name inside a nickname pair as well (M3) — unless its content is suffix-shaped, which S1 takes ahead of both. A lone marker has said nothing, and neither has one the colon spelling above glues to the name. A marker also says something about the name standing beside it: it announces a surname the bearer no longer uses, and that is only worth writing where there is a current one to tell it apart from (M4).

M1. Rationale: an enclosure the caller has declared to mean maiden
    holds the former family name; a recognized marker word inside it
    marks the clause and is not itself part of the name.
    With a delimiter pair configured for maiden names, its enclosed
    clause reads as the maiden name — unless the content is
    suffix-shaped, which S1 takes first — a leading recognized
    marker being dropped where the clause holds a word past it; a
    clause of nothing but its marker keeps its words, which may
    themselves be a surname (Nee).
    Clauses are independent: two enclosures read as one maiden name,
    each dropping or keeping its own marker. A pair configured for
    both maiden and nickname reads maiden. Configuring the pair is
    what this rule needs for a clause that does not announce itself
    — markerless content, and a lone marker alike, whether that
    marker is one word or several; a clause holding a word past its
    marker reads as the maiden name inside a nickname pair as well
    (M3), the suffix-shaped content S1 takes excepted there as it is
    here.
      "Jane Smith (née Jones)"  maiden-parens  →  maiden="Jones"
      "Jane Smith (Nee)"  maiden-parens        →  maiden="Nee"  · boundary
      "Jane Smith (Nee) (Jones)"  maiden-parens  →  maiden="Nee Jones"
      "Andrew Perkins (MBA)"  maiden-parens  →  suffix="MBA"  · boundary
      "Maria Kowalska (z domu)"  maiden-parens  →  maiden="z domu"  · boundary
    history: decisions.md#M1 · interacts: S1, M2, M3, M4 · implemented: nameparser/_pipeline/_extract.py, nameparser/_pipeline/_group.py

M2. Rationale: a maiden marker announces that what follows it is the
    former family name; the marker is an announcement, not a name.
    A recognized maiden marker standing after at least one name
    word takes the words after it — up to any suffix word, or the
    trailing roman numeral assign reads as the suffix (S2), both as
    written and as the take would leave the name, the word before
    the numeral being then the word before the marker, or a
    trailing word of the ambiguous credential class (S2), asked
    that same double way and stopping the take only where the rule
    reading the name left standing reads the word as the
    credential, and never the first word after the marker — as the
    maiden name, and
    the marker itself is dropped.
    Those last two stops are each asked TWICE for one reason: the
    count of words to spare includes the very words the marker
    removes, so a reading taken over the name as written can be
    wrong about the name the take would leave. WHICH rule does the
    reading depends on where the clause stands. Where the clause is
    in the part a trailing rule reads — a name with no comma, and
    the part before a SUFFIX comma, which that rule reads the same
    way — that rule is the reader. After a family comma it is the
    reading the end of the given part takes, where the comma has
    already settled the count and the writing decides alone. Before
    a family comma, and in a part after a second one, no trailing
    rule reads those words at all: the clause keeps them and says
    nothing about them.
    That the credential stop spares the first word after the marker
    is a deliberate divergence from what certain suffix vocabulary
    gets in the same position, where the marker declines and stays
    an ordinary word. The marker announces a name, and this class is
    the one carrying no evidence of which it is: its members are
    borne surnames as well as credentials, and nobody writes a
    credential straight after the marker, so a lone member reads as
    the name it was announced to be.
    A member ENDING a clause that some rule reads is reported where
    the clause KEEPS it (S2); one the clause gives up is reported
    where the reading that took it reports, so no word is reported
    twice and none goes unreported.
    That holds because a word the clause gives up reads as a
    post-nominal or the clause keeps it. The stop is right only
    where the released word ends the parse in the SUFFIX, so a stop
    that would put it in a name part is no stop and the clause keeps
    the word. What the take LEAVES BEHIND decides that, not the
    clause as written. Two shapes leave nothing that could read the
    word as a credential. A part whose other words are all
    post-nominals or titles has no name word left for a trailing
    slot to be the end of, and a part of nothing but credentials is
    read whole and asked nothing. And a join reached below the take
    — a particle chain (P2), or a bound given-name join (P5) — can
    absorb the released word into a name part before any trailing
    rule sees it, which would carry a word of the BIRTH name into
    the current one. In both the clause keeps the word, and reports
    it as it reports every member it keeps.
    Delimiters outrank every reading inside them. Where a recognized
    marker stands inside a delimited clause, the whole span is the
    maiden name whatever its last word is, and whether or not the
    pair is a configured maiden delimiter (M3): the writer drew the
    boundary, so no fork is called and nothing is reported. A word
    the writer left OUTSIDE the span is outside the clause and reads
    as it would anywhere else.
    A marker
    with nothing after it, or nothing before it, is just a word.
    A marker may be more than one word, and is then recognized only
    whole and only where its words stand together: its own first word
    standing without the rest is not that marker, and neither is one
    the writer divided from the rest by a bracketed clause or by a
    comma. Whether the first word takes anything on its own is a
    separate question with a separate answer — it does exactly when it
    is a recognized marker in its own right, and the longer entry wins
    wherever both could match.
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
      "Jane Doe nee Smith MA"     →  maiden="Smith"
      "Jane Doe nee Smith MA"     →  suffix="MA"
      "Jane Doe nee Smith Ma"     →  maiden="Smith Ma"  · boundary
      "Jane Doe nee MA"           →  maiden="MA"  · boundary
      "Jane Doe nee MA Smith"     →  maiden="MA Smith"  · boundary
      "John née Jones Smith MA"   →  maiden="Jones Smith"
      "Doe, Dr. nee Smith MA"     →  maiden="Smith MA"  · boundary
      "Berg, abdul nee Jones MA"  →  maiden="Jones MA"  · boundary
      "Jane Doe nee Smith DO DO"  →  maiden="Smith DO DO"  · boundary
      "Jane Doe (nee Smith MA)"   →  maiden="Smith MA"
      "Jane Doe (nee Smith Ma)"   →  maiden="Smith Ma"
      "Jane Doe (nee Smith) MA"   →  suffix="MA"
      "Jones née"                 →  family="née"  · boundary
      "née Jones"                 →  family="Jones"  · boundary
      "Jane van der Berg née Jones"  →  maiden="Jones"
      "Jane de la née Jones"         →  family="de la"
      "Jane van der Berg née"        →  family="van der Berg née"
      "Jane van der Berg née PhD"    →  family="van der Berg née"
      "Jane van der Berg née y Jones"  →  maiden="y Jones"
      "van der Berg, abdul née Jones"  →  maiden="Jones"
      "Maria Kowalska z domu Nowak"     →  maiden="Nowak"
      "Anna z Nowak"                    →  family="Nowak"  · boundary
      "Anna z (domu) Nowak"             →  family="Nowak"  · boundary
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
    Accepted: a bare acronym the reading declines is maiden text all
    the same — the writing decides this one (S2), and the count such
    a reading needs is taken over the name the take would leave
    rather than over the words as they stand.
      "John née Jones Smith Ma"        →  maiden="Jones Smith Ma"
    Accepted: a trailing title is not transparent inside a clause,
    and the two spellings disagree — the walk reads the trailing
    credential run and not the title chain behind it, so a title
    AFTER a member of that class hides it and a title before it
    does not.
      "Jane Doe nee Smith MA Prof."    →  maiden="Smith MA Prof."  · boundary
      "Jane Doe nee Smith Prof. MA"    →  maiden="Smith Prof."  · boundary
    history: decisions.md#M2 · interacts: P2, P3, P5, P6, R2, M1, S2, H1, H5 · implemented: nameparser/_pipeline/_group.py

M3. Rationale: an enclosure says nothing about whether it means
    maiden, but a recognized marker word inside it does — the clause
    announces itself, so the caller does not have to declare the
    pair.
    A bracketed clause whose content opens with a recognized marker
    and carries a word after it reads as the maiden name,
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
      "Jane Smith (née Jr.)"      →  suffix="Jr."
      "Jane Smith (née)"          →  nickname="née"  · boundary
      "Maria Kowalska (z domu Nowak)"  →  maiden="Nowak"
      "Maria Kowalska (z domu)"   →  nickname="z domu"  · boundary
    Accepted: the word taken after the marker is not tested for
    being a name word, so unlike M2's bare take this one does not
    stop at a suffix word — the same two words read one way
    bracketed and another way bare. This does not contradict the
    S1 example above: S1 asks whether the WHOLE clause is
    suffix-shaped, which the trailing period makes true of the one
    and false of the other, so only the V clause reaches this rule.
      "Jane Smith (née V)"        →  maiden="V"
    history: decisions.md#M3 · interacts: M1, M2, S1, N1 · implemented: nameparser/_pipeline/_extract.py

M4. Rationale: a maiden name is a FORMER family name, and a former
    one only means something beside a current one — nobody announces
    the surname they used to carry where there is no surname beside
    it to tell it apart from. So where a maiden name has been read
    out of a name and a single name word is left standing, that word
    is the surname the bearer uses now; writing the clause at all is
    what rules out the given-name reading O5's convention would
    otherwise leave it with. How the maiden name was written does
    not enter into it — a marker taking the words after it (M2), a
    marker-led clause (M3), and a clause in a pair the caller
    declared to mean maiden (M1) announce the same thing, and the
    last of those carries no marker at all.
    A maiden name standing beside exactly one name word makes that
    word the family name, whatever suffix or nickname stands beside
    it — an annotation beside the name is no part of the name, which
    is how H1 reads the same shape. Two kinds of word are beyond its
    reach, for one reason: the rule changes what POSITION would have
    decided, so it cannot overrule what a word already IS
    (mechanisms.md#TWO-LAYER-ASSIGN). A word the vocabulary has
    claimed as a given name keeps that reading, and so does a word
    read as an initial, which is nobody's family name. A name
    carrying a TITLE is H1's rather than this rule's, H1's
    given-name-title carve-out included, which keeps the word a
    given name. A nickname holds nothing off: where N3 has already
    named the family this rule finds nothing left to move, and where
    N3 declined — its count does not set a suffix aside — this rule
    names it. Where the maiden name stood does not matter, only what
    is left beside it: a marker inside the name takes the rest of it
    (M2), and one name word left that way is one name word.
      "Smith née Jones"           →  family="Smith"
      "Smith (née Jones)"         →  family="Smith"
      "Smith (Jones)"  maiden-parens  →  family="Smith"
      "Jane née Jones Smith"      →  family="Jane"
      "Smith née Jones PhD"       →  family="Smith"
      "abd née Jones"             →  given="abd"  · boundary
      "J. née Jones Smith V"      →  given="J."  · boundary
    history: decisions.md#M4 · interacts: M1, M2, M3, H1, N3, O5 · implemented: nameparser/_pipeline/_post_rules.py

## Commas & structure (C)

Background: a comma in a name signals one of two conventions — the listing form "Family, Given" or trailing credentials "Name, PhD" — and which is meant can only be judged from what stands after the first comma. Recognizing a credential run is by nature a vocabulary judgment, so this is the one structural decision that consults the suffix word lists. Which characters COUNT as the comma is part of the rule: the Arabic comma (U+060C) and the fullwidth comma (U+FF0C) both signal the listing form, while the ideographic comma (U+3001) is not a name-structure comma at all (#265).

C1. Rationale: a credential run after the comma means the name is in
    natural order with suffixes appended; anything else after the
    comma means the listing form.
    With a comma present, the name reads as trailing suffixes when
    the part after the first comma is entirely suffix words and more
    than one word precedes the comma; otherwise it reads as the
    listing form, the part before the comma being the family name.
    Only the part after the first comma decides.
    For the ambiguous credential class — a bare acronym the
    vocabulary marks as also an ordinary name, and a word admitted
    to the class by shape, which S3 defines and bounds — the
    count before the comma is of NAME words rather than of words:
    two or more of them read the part after the comma as the
    credential run, whatever case the name is written in. The count
    goes FIRST and written case is asked only after it: where two
    name words stand before the comma the part after it is the
    credential run however that part is written, and only where the
    count leaves the word a name — one name word before the comma —
    is the case read, capitals in a mixed-case name making it the
    credential there too (S2). A decision either way at this comma
    is reported. It is one of TWO places the comma's own decision is
    reported, the other being the word trailing the given part after
    it (S2), which is a second decision about a second word and never
    the same fork twice; an attachment decided after a family comma
    (P6) reports on its own. C2's comma-structure flag reports what the
    parse could not recognize, not a fork it called.
    By default a recognized suffix word counts
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
    a name and so a middle initial. Both branches then ask that the
    generation slot still be open: where a further comma has already
    named the suffix, a single letter ending the GIVEN part has no
    generation left to be, and stays a middle initial — with a
    period or without, and whether a name word or another suffix
    word stands before it. Only the given part is touched; a part
    after the comma that is nothing but suffix words is the
    credential run, and a letter in it continues that run up to the
    further comma. Longer suffix words are not in question either
    way, and the strict knob above still vetoes the initial-shaped
    ones, so the run ends at them there.
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
      "Smith, John PhD I."        →  suffix="PhD I."
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
      "John Smith, MA"            →  suffix="MA"
      "John Smith, Ma"            →  suffix="Ma"
      "Smith, MA"                 →  suffix="MA"
      "Smith, Ma"                 →  given="Ma"
      "John Smith, Ed"            →  suffix="Ed"
      "Davis Royce, Ed"           →  suffix="Ed"
      "Royce, Ed"                 →  given="Ed"  · boundary
      "Smith Jr., MA"             →  suffix="Jr., MA"
      "Smith Jr., Ma"             →  given="Ma"  · boundary
      "John Smith, A.B."          →  suffix="A.B."
      "John Smith, A.B."  unlisted_dotted_suffixes-off  →  given="A.B."
      "Smith, A.B."               →  given="A.B."  · boundary
    Accepted: a word of both the title and the unambiguous suffix
    vocabulary reads as the postnominal after a family comma in
    every spelling, the honorific's too — position decides for the
    duals, and the slot is postnominal.
      "Smith, Ms."                →  suffix="Ms."
      "Smith, Ms. Jane"           →  title="Ms."
    Accepted: the vocabulary question above — is the part after the
    comma nothing but suffix words — is asked a second time, without
    the word-count condition, to decide whether a glued East Asian
    honorific standing before a family comma comes off. That
    composition is tolerated input rather than contract — a comma
    between a family name and a given name is no part of CJK writing
    — so the precedence is stated at W3, with its examples, and not
    here. It is also the one consequence of this question Latin
    script cannot witness, nothing there being glued to the end of a
    name — which is why this clause carries no example of its own.
    Accepted: a delimiter core the policy names (T1) is a word here,
    not structure — v1 applied the delimiter to the suffix-comma
    form alone, and that limitation is kept as parity: "Smith, RN -
    CRNA" reads given "RN" under the policy as without it.
      "John Smith, LEED AP"       →  family="Smith"  deviates: #291 (today: family="John Smith")
    Accepted: the further-comma qualifier carries no example line of
    its own. It discriminates PAIRS and spans both branches, so
    exemplifying it means a with-comma partner for each — every one
    of them a name entering the rules corpus for behavior that has
    not moved since v1. Its executable witness is instead the pair
    already standing in the v1-style bank,
    tests/test_suffixes.py's
    test_roman_numeral_i_after_single_initial_lastname_comma_format
    and test_roman_numeral_i_with_explicit_suffix_comma_stays_a_middle_initial.
    Read the examples above with the qualifier in hand: `Smith, John
    V` reads the suffix and `Smith, John PhD I.` continues the run,
    while adding a suffix comma after either turns that same letter
    into the middle initial.
    history: decisions.md#C1 · interacts: H2, P6, W3, S2, S3 · implemented: nameparser/_pipeline/_segment.py, nameparser/_pipeline/_assign.py, nameparser/_pipeline/_group.py

C2. Rationale: text beyond the recognized comma parts should be
    taken in without silent guessing.
    Parts beyond the second are consumed as suffixes either way; a
    non-empty extra part that is not entirely suffix words is
    flagged as a structural ambiguity rather than rejected — parsing
    never fails on content. An empty part between doubled commas is
    consumed silently.
    A part the parse reads as a credential run by some route other
    than the suffix vocabulary is recognized and is not flagged: a
    run of ambiguous acronyms whose written case leans credential
    (S2), and a run every word of which is an unlisted DOTTED word
    the position reads as a credential (S3). This is the one place
    the ambiguous class QUIETS a report rather than adding one, and
    it is narrow in two ways that the examples below pin. A member
    whose written case does not lean CREDENTIAL keeps the flag,
    whether the name is written in one case so that nothing leans at
    all, or the member is written the way a name is written. And
    S2's other by-shape half, the unlisted all-caps word, does not
    reach here under its switch either: the shape a tail segment is
    recognized by is the dotted one alone.
      "John Smith, MD, Bart"      →  suffix="MD, Bart"
      "John Smith, MD,, Jr."      →  suffix="MD, Jr."  · boundary
      "John Smith, MD, R.A.I."    →  suffix="MD, R.A.I."
      "John Smith, MD, R.A.I."    →  ambiguities=()
      "John Smith, MD, R.A.I."  unlisted_dotted_suffixes-off  →  ambiguities=("comma-structure",)
      "John Smith, MD, Ma"        →  ambiguities=("comma-structure",)  · boundary
      "Steven Hardman, MD, DO, DDS"  →  ambiguities=()
      "STEVEN HARDMAN, MD, DO, DDS"  →  ambiguities=("comma-structure",)  · boundary
      "John Smith, MD, XYZ"  unlisted_caps_suffixes-on  →  ambiguities=("comma-structure",)
    history: decisions.md#C1, decisions.md#S2 · interacts: C1, S2, S3 · implemented: nameparser/_pipeline/_segment.py

## Name order (O)

Background: written name order varies by convention: given-first (the library's default reading), family-first, and family-first with the given name last (Vietnamese, where the person is called by the last element, given names are frequently two syllables — the given_names view stays correct wherever the internal boundary falls — and quốc ngữ is Latin script, so no native-script signal exists at all). The order is declared by the caller or a locale pack, never detected — but a few conventions leave a recognizable trace in the name itself. Patronymics are one: East Slavic names carry a father's-name derivative with distinctive endings between given and family, and Turkic names use a standalone marker word ("oglu" son-of, "qizi" daughter-of) after the father's name. Where such a trace is present and unambiguous, an opted-in parser can restore the intended reading from a family-first listing.
A declared order is a property of the DATA SOURCE rather than of any one string: the caller sets it to match how their records are written, and it governs what no vocabulary and no script license has already claimed (O4). A declared FAMILY-FIRST order outranks what the parser could infer from the shape of a particular name; the given-first reading is the parser's DEFAULT rather than a declaration it can tell apart from one, and the traces above are what refine it (O1, O2). And the declaration yields where a name's own script settles the order instead (W4, where a name written wholly in an East Asian script reads family-first whatever order the caller declared). Two consequences run through this document. Under the default given-first order a string opening with a never-given particle is a surname whose given name is simply absent, so the fold takes the rest of it (P1). Under a declared family-first order the caller has already said that what follows the family is not more surname — so the fold stops there, and the rotations below, whose whole job is to RESTORE the default reading from a family-first listing, have nothing left to restore. A shape neither order settles is the family comma's job, and the parser does not guess at it.

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
    The restoration is the default order's work: it recovers the
    given-first reading a family-first listing hides, so where the
    caller has DECLARED a family-first order there is nothing left
    to restore and position decides.
      "Сидоров Иван Петрович"  [ru]  →  family="Сидоров"
      "Sidorov Ivan Petrovich Jr."  [ru]  →  family="Sidorov"
      "Иван Петрович Абрамович"  [ru]  →  family="Абрамович"  · boundary
    Accepted: under a declared family-first order the readings part
    on natural-order input, and the declaration wins. A family-first
    listing reads the same either way under FAMILY_FIRST — the first
    example above is that same parse with FAMILY_FIRST declared,
    and under FAMILY_FIRST_GIVEN_LAST the listing's given and middle
    swap, so only the family is invariant — while with East Slavic
    handling active and FAMILY_FIRST declared the natural-order
    Иван Петрович Сидоров reads family Иван, given Петрович, middle
    Сидоров. That is the caller's declaration being honored on input
    they said was written family-first, not a defect (#384). No
    registered example annotation combines a pack with an order, so
    the parse is pinned in tests/v2/test_locales.py instead, and
    decisions.md#O1 records why options 2 and 3 were declined.
    history: decisions.md#O1 · implemented: nameparser/_pipeline/_post_rules.py

O2. Rationale: a Turkic patronymic marker is a separate word that
    follows the father's name; a four-word name ending in one is a
    family-first listing.
    With Turkic patronymic handling active and no comma in the name,
    a name of exactly four name words — titles, suffixes and
    nicknames aside — ending in a standalone patronymic marker reads
    family-first: the first name word is the family name, and the
    marker stays beside the father's name in the middle.
    The scope is O1's: the restoration recovers the default reading,
    so a declared family-first order stands in its place.
      "Ali Ahmad Vali oglu"  [tr_az]  →  family="Ali"
      "Ali Ahmad Vali oglu Jr."  [tr_az]  →  family="Ali"
    Accepted: any other count of name words keeps its positional
    reading, even when that leaves the marker itself in a name
    field.
      "Ali Ahmad oglu"  [tr_az]  →  family="oglu"  · boundary
    Accepted: the order scope above has this rule's own consequence
    reached by a second route — with Turkic handling active and
    FAMILY_FIRST_GIVEN_LAST declared, Ali Ahmad Vali oglu reads
    given oglu, the marker standing in a name field because the
    declaration put the name's last word there (#384).
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

O5. Rationale: O4 reads a name by comparing where its words stand,
    and a name of exactly one name word gives it nothing to compare
    — the first name word is also the last, so the rule that decides
    every longer name is silent here. Nothing in such an input says
    whether the word is a given name or a family name: both readings
    fit it equally well, and the library still has to report one.
    A name of one name word that nothing else has decided reads that
    word as the given name under the default given-first order, and
    as the family name under a declared family-first one. That is a
    convention rather than a determination — the same input has to
    read the same way every time, so one of two equally consistent
    readings is fixed in advance — and it is not evidence about the
    word. Every rule that DOES decide such a name outranks it, and
    each of them carves out a case it declines to decide — where the
    convention is what is left. A title makes the word the family
    name (H1), except a given-name title, which addresses by given
    name; a nickname beside it does the same (N3), except where a
    suffix stands beside them too, which its count does not set
    aside; and a maiden name beside it does the same (M4), except
    where the vocabulary or the word's own shape has claimed the
    word already. The convention is reported: a name whose one name
    word nothing else decided carries a `given-or-family` ambiguity
    naming the field the convention chose. The report is exactly as
    narrow as the convention, so every rule named above silences it
    where it fires, a family comma — a comma with a name segment
    after it — silences it, a script whose own convention settles
    the order (W4) silences it, and so does the word's own claim — a
    particle, a bound given name, an initial's shape. A comma with
    nothing after it names no family and silences nothing, so
    `سلمان،` and `Smith,` report where `Smith, Andrew` does not. A
    comma with only a TITLE after it names no family either, but the
    title still decides the field wherever it stands, so `John V, Dr.`
    is silent for H1's reason and not the comma's. A word with no
    letter or digit in it is no name word and
    reports nothing (A2). Where the one name unit carries title
    vocabulary in a word beside the one it places, or is itself title
    vocabulary left standing by the title peel, the doubt reported is `title-or-name`
    instead, which H4 states — so a title silences THIS kind, not
    every report at the site.
      "Smith"                     →  given="Smith"
      "Garcia"  family-first      →  family="Garcia"
      "Sir John"                  →  given="John"
      "'Smitty' Jones Jr."        →  given="Jones"
      "abd née Jones"             →  given="abd"
      "Mr. Johnson"               →  family="Johnson"  · boundary
      "'Smitty' Jones"            →  family="Jones"  · boundary
      "Smith née Jones"           →  family="Smith"  · boundary
      "Andrew"                    →  ambiguities=("given-or-family",)
      "Garcia"  family-first      →  ambiguities=("given-or-family",)
      "Juan & Garcia"             →  ambiguities=("given-or-family",)
      "'Smitty' Jones Jr."        →  ambiguities=("given-or-family",)
      "Smith Jr."                 →  ambiguities=("given-or-family",)
      "Dr. Smith"                 →  ambiguities=()  · boundary
      "Sir John"                  →  ambiguities=()
      "Smith née Jones"           →  ambiguities=()
      "abd née Jones"             →  ambiguities=()
    history: decisions.md#O5 · interacts: O4, H1, N3, M4, H4, W4, P3, A2 · implemented: nameparser/_pipeline/_assign.py

## Scripts & writing systems (W)

Background: script-conditional behavior is permitted exactly where the writing system itself — not statistics about it — settles the convention; a language can never be inferred from Latin-script text, because transliteration destroys the signal. The facts this section builds on: Chinese and Japanese both write the family name first in native script, so the script settles the order without knowing the language. Hangul is written by exactly one language and Korean family names are a small closed census set. Han text does not identify its language — a Chinese surname list would divide Japanese 高橋一郎 as 高 + 橋一郎 — which is why Han division is opt-in and there is no Korean pack to opt into. Hiragana never transcribes a foreign name (transcriptions are katakana alone), so kanji-plus-kana is a Japanese name in Japanese order, while wholly-katakana is predominantly a transcribed foreign name already in given-first order. Real Chinese text is unspaced (毛泽东); the spaced 毛 泽东 is an artifact. A fuller narrative lives in docs/usage.rst's East Asian section. One fact carries its own consequence: none of the three writing systems marks the family name with a comma — position in the written form is what identifies it, so a comma standing between the family name and the given name is a listing convention carried in from elsewhere rather than a form the script produces. That is why the rule reading one (W3) is tolerated rather than normative. CLDR's own locale data says the same where a contrary convention would have had to appear: across its ko, zh and ja personName patterns not one of the 126 pattern strings carries a comma of any width, the surname-first referring patterns separating surname from given by a single space, and the only comma in reach belongs to the locale-neutral root's sorting format — a list-ordering format, which ko and zh override comma-free and ja all but one inherited slot (decisions.md#cjk-comma-demotion carries the pull verbatim, with its URLs, its commit and its date). A full stop of any width — the ASCII period, the fullwidth ．, the ideographic 。 and its halfwidth ｡ — glued after a script-written word is punctuation and not part of the word: it is invisible to the script reading and to the vocabulary, and it stays in the text on the word it arrived with, because no East Asian script writes an initial or an abbreviation with a period (#322, #323; decisions.md#cjk-full-stops). A stop glued BEFORE the word is punctuation to the vocabulary lookup, which folds both edges away, so .씨 is still the honorific. The classification fold that feeds the two division sites reads the trailing edge only, so a word wearing a leading stop is given no script at all and never becomes a surname site: .김민준 stays one whole word, given, no script rule reaching it. The honorific peel (W2) is not gated by that fold — the tail alone is its license — so it reads such a token regardless of a leading stop, and its own trailing-edge fold is what decides there: .김민준씨 peels to .김민준 and 씨, and .김민준씨. peels to .김민준 and 씨. (tests/v2/pipeline/test_script_segment.py's test_the_peel_reads_the_trailing_stop_only).

W1. Rationale: hangul is monoglot Korean and its surnames are a
    closed census set, so an unspaced hangul name divides at a
    certain point; Han carries no such certainty by default.
    An undivided word in the family position of a name written in
    an activated script divides after a recognized surname, the
    longest recognized surname first; where the vocabulary
    recognizes nothing, an optional segmenter may divide instead,
    and with neither the word stays whole rather than divide in a
    wrong place. Korean division is active by default; Han division
    is opt-in. A segmenter — unlike the vocabulary, which ignores
    spacing but not the interpunct (the Accepted below) — is
    consulted only for a name whose written form is wholly
    undivided, a spaced honorific counting as a written division
    (decisions.md#W3 records what that trade keeps and costs).
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
    history: decisions.md#W1 · interacts: W3 · implemented: nameparser/_pipeline/_script_segment.py

W2. Rationale: some East Asian honorifics glue directly onto the end
    of the name (田中さん); a glued word peels off only if it could
    never itself end a name, so the listed vocabulary carries its
    own license and needs no other gate.
    A listed honorific glued to the end of the name's last name
    word splits off once and reads as a suffix. A part that is not
    name text — a post-nominal word standing on its own — is never
    the name's end: the split-off steps past it to the name word
    behind, and never dissects it.
      "田中さん"                  →  suffix="さん"
      "김민준씨"                  →  suffix="씨"
      "김민준 박사님"             →  suffix="박사님"
      "马丁·路德·金씨"            →  suffix="씨"
      "김지양"                    →  suffix=""  · boundary
      "선생님"                    →  family="선생님"  · boundary
      "王君"                      →  family="王君"  · boundary
    history: decisions.md#W2 · interacts: W3 · implemented: nameparser/_pipeline/_script_segment.py

W3. Rationale: a family name declared by a comma is the writer's
    own division, and re-dividing it would invent a boundary nobody
    drew — but none of the East Asian writing systems declares a
    family name that way (the Background above), so every input this
    rule reads is a listing convention wrapped around a name whose
    own script has already arranged it — the comma that declares the
    family name, and the punctuation such a listing carries in with
    it. What follows describes what the parser does with such input;
    it does not promise it.
    Under a family comma the pre-comma text is the family by
    declaration and never divides, and the post-comma side is given
    text with no family to find; only the honorific split-off (W2)
    crosses the comma, an honorific being no part of the name on
    either side — the crossing is stated here rather than in W2
    because it is a claim about the comma, and the comma is the part
    nobody's writing system produces. Which side the split-off takes
    it from is decided by the SHAPE of the part after the comma, not
    by which of C1's two readings that part selects — a one-word
    family reads the listing form either way. A part that is nothing
    but suffix words is not the name's end: it is declined as the
    site, and the split-off falls back to the part before the comma
    and takes the honorific there, provided that part offers a site
    of its own. Any other part — a title, a name word — IS the
    name's end, and a glued honorific before the comma stays glued.
    The vocabulary question is C1's own, asked without C1's
    word-count condition: the two differ in what else they require,
    not in what they ask of the words — the written-case evidence
    S2 reads included, so a post-comma acronym the case leans
    credential declines the side it stands on here exactly as it
    reads as the credential there, and the honorific comes off the
    part before the comma as it does behind a settled credential.
    A period the listing leaves
    behind is not what licenses the step past a post-nominal word,
    and it is not ignored either. The step is W2's, taken on the
    vocabulary alone and taken with no punctuation anywhere in the
    input; a period on a SEPARATE post-nominal word rides along into
    the suffix and moves no division (田中さん 様. divides where
    田中さん 様 does). A period glued to the honorific's OWN word
    rides with the honorific: the split-off matches the listed tail
    through it and cuts before it, so 田中さん. and 김민준씨. divide
    where 田中さん and 김민준씨 do (#323; until 2026-09-10 each read
    as a title, measured 2026-09-05 and pinned by nothing, which is
    why the move was free), and a period-marked Han opener divides
    as its stop-less spelling does, 田中. 太郎 reading family-first
    — the reading H2's Accepted clause vetoes a title into, carried
    here because an edge full stop makes it tolerated input like the
    rest of this block. All three are case rows now, tolerated, and
    the sentence reports them rather than promising them, even by
    this rule's standard.
    decisions.md#cjk-comma-demotion carries the parses.
      "남궁민수"                  →  family="남궁"
      "지훈, 남궁민수"            →  given="남궁민수"
      "남궁민수, 지훈"            →  family="남궁민수"  · boundary
      "田中さん, Dr."             →  family="田中さん"
      "田中さん, PhD"             →  suffix="さん, PhD"
      "Kim김민준씨, MA"           →  suffix="씨, MA"
      "田中さん 様."              →  suffix="さん 様."
      "김민준씨."                 →  suffix="씨."
      "田中. 太郎"                →  family="田中."
    tolerated: native CJK writing has neither a family-comma convention nor an edge full stop of any width on a name word, so the five comma lines above and the three period lines under them illustrate current behavior — changeable without notice — rather than promise it; the line carrying neither, beside them, is W1's claim, which is normative. All eight stay watched at every released baseline on the differential's radar tier (tools/differential/corpus_cjk_tolerated.jsonl, projected from the `tolerated` rows of tests/v2/cases.py) instead of its contract tier, and those rows pin them at HEAD.
    history: decisions.md#W3 · interacts: W1, W2, C1, H2 · implemented: nameparser/_pipeline/_script_segment.py

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
    written with commas keeps them. The separator is the comma the
    writer typed, read off the words' positions once their roles are
    known; a delimiter the configuration names is a separator too,
    and so is any name word standing between two post-nominals.
      "Dr. Juan Q. Xavier de la Vega III"  →  family="de la Vega"
      "Hassan, Mohamad Ahmad Ali"  middle_as_family  →  family="Ahmad Ali Hassan"
      "Hassan, Mohamad Ahmad Ali"          →  family="Hassan"  · boundary
      "Smith, MD PhD"                      →  suffix="MD PhD"
      "John Smith MD PhD"                  →  suffix="MD PhD"
      "John Smith, MD, Bart"               →  suffix="MD, Bart"
    Accepted: a suffix value handed to revise() derives its entries the
    same way, from the value's own commas, so a name's rendered suffix
    revises back to itself wherever the value's words read as the
    whole name read them — a glued CJK honorific peels off an initial
    in a bare value where the whole name kept it glued, one corpus
    name of the 372 with a suffix (decisions.md#C1, 2026-09-06, which
    counted 368 of 1117 then; re-measured 2026-09-10 with this
    bundle's rows in the corpora, 372 of 1156 distinct names and the
    same single failure). A delimiter the configuration names parts a
    value only where the value's own words, read as a name, give it a
    tail segment for the core to be dropped on; a run of post-nominals
    has none, with or without a comma of its own, so there the
    delimiter stays a word of the run — write a comma at the boundary
    instead. Stated without an example line because every line here
    names an input string, and this shape needs a field revised after
    the parse.
    history: decisions.md#C1 · interacts: O3, P6, R3 · implemented: nameparser/_parser.py, nameparser/_pipeline/_post_rules.py, nameparser/_types.py

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
    so a base that is one contributes nothing even then. That
    carve-out is stated for the middle and base family words; the
    GIVEN group is not settled here. A conjunction written among
    given names does initial today, and this document does not yet
    say whether it should — because two of its own rules answer
    differently and neither answer has been taken: this rule counts
    name words, while P3 makes a connective and its neighbours ONE
    name word, so a joined given group owes one initial under P3 and
    one per joined name word under the carve-out. Until that is
    decided the given group's answer is pinned-but-undocumented
    rather than specified, and no line below asserts it.
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
    A family that is ALL particles therefore contributes its words
    rather than nothing: they are the base (R2), so they initial.
      "Juan van der"              →  initials="J. v. d."
      "Juan de y"                 →  initials="J."
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
    other view does not have. decisions.md#R3 carries what all of it
    costs and where it is pinned.
    Accepted: the unsettled given-group answer above is neither rare
    nor hypothetical — 26 of the corpus names carry a conjunction
    among the given names (measured 2026-09-13; recompute by parsing
    the deduped corpus*.jsonl glob and keeping every name with a
    GIVEN-role token tagged "conjunction"), every one of them
    reachable from the default vocabulary, and it has initialed since
    1.4.0. It carries no marked deviation, for the reason that
    mechanism exists: a
    marker states the INTENDED value, and one name, "John and Jane
    Smith", has four candidates. Today gives "J. a. J. S."; the
    carve-out read as written gives "J. J. S."; P3's one-name-word
    join gives just "J. S."; and 1.4.0 gave "J a J. S.". Marking it
    would put an invented value in a normative document and hold
    the parser to it. #461 asks the neighbouring question about the
    all-particle base and does not own this one; decisions.md#R2
    carries the population and the measurements.
    history: decisions.md#R3 · interacts: O3, P3, P6, R1, R2, R4 · implemented: nameparser/_render.py, nameparser/_facade.py

R4. Rationale: case repair is a display concern, applied only on
    request and never destructively.
    Case repair returns a repaired copy and never mutates the parse.
    Where it acts at all — R5 decides where — the copy honors the
    casing a vocabulary entry records (Ph.D.) and the Mac/Mc
    convention (McDonald), not only ordinary word-by-word casing, and
    a part whose every word is particle vocabulary is repaired as
    ordinary name words, since none of them is doing a particle's
    work there (R2). A CONJUNCTION keeps its lowercase even inside
    such a part, being no name word in any part — the carve-out R3
    states for initials. A name already written the way repair would
    write it comes back unchanged, measured by repair's own
    conventions rather than by the bearer's. A spelling written in a
    single case is repaired even where its bearer meant it, because
    nothing in the text marks it as a choice; where the text does
    mark one, R5 defers to it.
      "juan mcdonald"             →  capitalized="Juan McDonald"
      "Juan McDonald"             →  capitalized_forced="Juan McDonald"
      "ANH DO"                    →  capitalized="Anh Do"
      "anh van do"                →  capitalized="Anh Van Do"
      "john smith phd"            →  capitalized="John Smith Ph.D."
      "juan de la vega"           →  capitalized="Juan de la Vega"  · boundary
    Accepted: the clause reaches a part the parser read. A field
    spliced in as raw text after the parse carries no reading of its
    own, so a family set that way to "de la" stays lowercase where
    those same two words parsed from a name are repaired to "De La".
    That is the boundary between splicing text into a field and
    revising a field through the parser — revise() classifies the
    value, so the repair follows it — rather than a gap between them.
    It is also a limit and not a regression: a spliced-in family was
    repaired exactly this way before the clause existed. Stated
    without an example line because every line here names an input
    string, and this shape needs a field edited after the parse.
    Accepted, and the reason the boundary is drawn per question
    rather than per field: the conjunction carve-out reaches a word
    the parse read as a conjunction, and where the parse read nothing
    at all it reaches what the vocabulary says. A word of that
    vocabulary standing inside a longer written word is not a
    conjunction, because the parse read that word as one ordinary
    name word — but a field spliced in as raw text was read by
    nobody, so repair asks the vocabulary and a family set to "de y"
    keeps its "y" lowercase. Whether a word is the conjunction or an
    initial is a property of the word, which a vocabulary can answer;
    whether a particle is acting as a particle is a property of the
    whole part, which the parse settles and records; re-deriving it
    needs a reading on every word of the part, and a spliced field
    has none on any, so that half falls through to particle treatment
    and the "de la" boundary above stands. Initials are the contrast
    worth knowing, and R3 states it — but ask which initials view,
    because the two answer oppositely. The parsed name's own view is
    handed no vocabulary at all, so it falls back on neither question
    and a spliced field's every word initials. The v1 facade's view IS
    handed one: the connective question falls back to the helper this
    rule uses, while the particle question is never asked of the
    parse in this view at all — a live vocabulary lookup for every
    word, backed or spliced alike — so a family spliced to "de la
    vega" initials "j. v." there against the parsed view's "j. d. l.
    v.". revise() classifies the value and crosses both questions, in
    both of the parsed name's views: a middle revised to "e-f"
    repairs to "E-F" as the parsed name does, where splicing the same
    text in gives "e-F".
    history: decisions.md#R4 · interacts: R2, R3, R5 · implemented: nameparser/_render.py

R5. Rationale: mixed case is evidence that the writer cased the name
    deliberately, and a repair cannot tell a deliberate spelling from
    a mistaken one. A name written wholly in one case leaves the
    repair no such evidence to read either way — the writer who
    always writes lowercase is indistinguishable from the writer who
    could not be bothered — so repair proceeds there, which is a
    choice about how to act absent evidence rather than a claim that
    nothing can be lost by it.
    Case repair acts only on a name written entirely in one case. A
    name written in more than one case is kept as it was written,
    and whether that casing is right does not enter into it, unless
    repair was asked for anyway.
      "juan mcdonald"             →  capitalized="Juan McDonald"
      "SHIRLEY MACLAINE"          →  capitalized="Shirley MacLaine"
      "Shirley Maclaine"          →  capitalized="Shirley Maclaine"
      "Shirley Maclaine"          →  capitalized_forced="Shirley MacLaine"  · boundary
    history: decisions.md#R5 · interacts: R4 · implemented: nameparser/_render.py

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
