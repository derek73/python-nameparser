# P3 — connectives

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
    have gone the other way, and is reported — unless no name word
    of its part stands to its right, nothing at all or only
    post-nominals and titles, where it connects nothing and there is
    no other way for the call to go: it is not reported, and where
    S10 reads it as a numeral S10's report is the one.
    The joined part is ONE name word wherever another rule counts
    them, so a rule taking "one name word" takes the whole join and
    never half of it — except C3's count of the words before a comma,
    which counts particle surnames alone and states why.
    A connective counts as a name word wherever this rule counts them,
    whatever else the vocabulary says the word is, where it is placed
    to join. A word can be a connective and a generation at once — the
    Catalan link is also the roman numeral one — and counting it as
    the generation would let a connective raise the bar for its own
    join, so the shortest linked name, which is the commonest one,
    would be the only one that failed to link; while counting it as a
    connective where it joins nothing lowers the bar for a different
    connective's join instead.
    A connective that is also generational vocabulary joins only where
    a name word stands on each side of it — a word the rest of the
    parse reads as a name word rather than as a generation, a
    credential or an honorific, looked for past any run of
    connectives standing between. A connective with nothing to its right is connecting
    nothing, and a word of that vocabulary ending a name, or standing
    before the credential a name ends with, is the generation it also
    spells wherever S10 reads one there.
    A separator the caller declared, standing in a trailing suffix
    part, ends the search there as a comma would, so a connective
    never joins across it (C10); anywhere else it is a word.
    Both questions this rule asks of a name — how many words it has,
    and whether it is written in one case — are asked of the name's
    OWN words: a maiden marker taken as one, and the words it takes
    (M2), are not among them, and neither is a delimited clause (N1,
    M1). So a clause beside the name changes neither whether the
    connective joins nor how a letter in the name reads, and a letter
    inside such a clause is the clause's word, read by T4 and not by
    this rule. The two questions part at one point: a
    marker the pass declines and leaves as a word (M2) is a word, and
    counts toward the three — but its case is still not asked.
    That span is not this rule's alone: wherever another rule asks
    the case question — the suffix slot (S6) and the post-comma slot
    (C4, C6) — it is asked of these same words, so the answer is taken
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
      "Josep Carod i Rovira"      →  family="Carod i Rovira"
      "Carod i Rovira, Josep"     →  family="Carod i Rovira"
      "Josep i Rovira"            →  middle="i"
      "John Quincy Smith i"       →  suffix="i"
      "Carod i"                   →  suffix="i"
      "carod i"                   →  ambiguities=("suffix-or-name",)  · boundary
      "jose e phd"                →  ambiguities=()  · boundary
      "smith, john e phd"         →  ambiguities=()  · boundary
      "john van e phd"            →  ambiguities=()  · boundary
      "Josep Lluis Carod i III"   →  suffix="i III"
      "Carod y de Rovira i"       →  middle="y"
      "John й Smith"              →  middle="й"
      "É. y É. Smith"             →  given="É."
    Both exceptions are about the written FORM, not the word: the
    three-word carve-out counts letters, so a symbol connective joins
    at any length, and it reaches every single-letter connective the
    vocabulary holds — Catalan i and Cyrillic и/і/й and Arabic و as
    well as y and e. The initial reading counts letters too, and asks
    one more question of them: a letter with no case at all (و) can be
    written against nothing, so it never reads as an initial. A Cyrillic
    capital has case but is not the shape an initial is written in —
    Cyrillic abbreviates with a dotted letter — so in a name of more
    than one case it joins, the reading #267 blessed, and in a name
    of one case it takes the vocabulary's answer like any other cased
    letter. A letter written as a base letter plus a combining mark
    (NFD) that composes to one character is one letter to every
    count here, and a period-marked initial written that way is one
    initial (#665), so the last two examples above, both typed
    decomposed, read as their composed twins.
    Which single letters a tradition actually wants joined differs by
    language, and the marked set is where that answer lives: "y" is
    the commonest Hispanic compound and stays out of it, while "e" and
    Catalan "i" are both common bare initials and are the two entries
    shipped. A caller with Portuguese data removes "e"; a caller with
    Catalan or Polish data removes "i"; a caller with Dutch data adds
    the letter "y" to it.
    The initial reading is visible beyond the fields, on the two
    derived views: parse("john e smith").initials() gives "j. e. s."
    and .capitalized() gives "John E Smith", where the connective
    reading gave "j. s." and "John e Smith" — a connective
    contributing no initial (R3) and keeping its lowercase (R4),
    where an initial does neither. The v1 facade's initials() reads
    the same parse, so HumanName("john e smith").initials() is
    also "j. e. s."; #528 closed the split and decisions/P3
    records it.
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
    after it to T4 rather than to the one-case fork, so a letter
    there reads as the initial its capital is, in both spellings,
    where the fork would have joined it: both "DR. NÉE JUAN Y LOPEZ"
    and "dr. née juan y lopez" read middle "JUAN Y" with the letter
    an initial. A clause's words are
    read by T4 the same way, so such a letter takes the same tag in
    the two spellings.
    Accepted rather than repaired: classify cannot know what group
    will decline, and a clause's words are read by the clause's own
    rules.
      "Хосе И Мария Сантос"       →  given="Хосе И Мария"
    H1 is the counting rule that shows the one-word clause today: a
    title plus the join reads the whole join as the family, where the
    same two words unjoined are two name words and H1 does not fire.
    P1's leading run is the second (#395, landed): its run takes
    the "Vega y Santos" join whole or stops before it.
    Signal: a neighbor: a connective between name words + a count and a case contrast: the name's words and case, for a single-letter connective
    history: decisions/P3 · interacts: H1, P1, M2, R1, R3, R4, C3, C4, C6, C7, C10, S6, S10, T4 · implemented: nameparser/_pipeline/_assemble.py, nameparser/_pipeline/_classify.py, nameparser/_pipeline/_comma.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_post_rules.py

