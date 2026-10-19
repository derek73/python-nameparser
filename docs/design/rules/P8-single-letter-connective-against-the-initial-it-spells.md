# P8 — a single-letter connective against the initial it spells

P8. Rationale: where a name is written in more than one case, a
    bare Latin capital standing alone is how an initial is marked
    and a bare lowercase letter is how it is not; a name written
    wholly in one case marks nothing, so there the vocabulary says
    which letters read both ways.
    A single-letter connective reads as an initial where the writing
    says so: written as a bare Latin capital in a name that is not written
    wholly in one case, or — in a name written wholly in one case,
    where nothing says so — where the letter is one the vocabulary
    marks as reading both ways.
    Read as an initial, it is no connective and never joins (P3).
    A letter the vocabulary marks as reading both ways, read as an
    initial in a name written wholly in one case, is a call that could
    have gone the other way, and is reported — unless no name word
    of its part stands to its right, nothing at all or only
    post-nominals and titles, where it connects nothing and there is
    no other way for the call to go: it is not reported, and where
    S10 reads it as a numeral S10's report is the one.
    Case is asked of the name's own words, the span P3 states.
      "Jose E Maria Santos"       →  middle="E Maria"
      "jose e maria santos"       →  middle="e maria"
      "Jose e Maria Santos"       →  given="Jose e Maria"
      "JUAN GARCIA Y LOPEZ"       →  family="GARCIA Y LOPEZ"
      "juan garcia y lopez"       →  family="garcia y lopez"
      "john e smith"              →  middle="e"
      "carod i"                   →  ambiguities=("suffix-or-name",)  · boundary
      "jose e phd"                →  ambiguities=()  · boundary
      "smith, john e phd"         →  ambiguities=()  · boundary
      "john van e phd"            →  ambiguities=()  · boundary
      "jose e maria santos"       →  ambiguities=("conjunction-or-initial",)
    The initial reading counts letters, as P3's carve-out does, and
    asks one more question of them: a letter with no case at all (و)
    can be written against nothing, so it never reads as an initial.
    A Cyrillic capital has case but is not the shape an initial is
    written in —
    Cyrillic abbreviates with a dotted letter — so in a name of more
    than one case it joins, the reading #267 blessed, and in a name
    of one case it takes the vocabulary's answer like any other cased
    letter.
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
    also "j. e. s."; #528 closed the split and decisions/P8
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
    Signal: a case contrast: a single-letter connective's case against the name's own words
    history: decisions/P8 · interacts: P3, T4, M2, M4, R3, R4, S10 · implemented: nameparser/_pipeline/_assemble.py, nameparser/_pipeline/_classify.py
