# P3 — connectives

P3. Rationale: connective words ("y", "of the") bind name words into
    one name part; but a single letter in a short name is more
    likely an initial than a connective.
    A recognized connective joins its neighbors into one name part,
    connective runs included — except a single-letter connective in
    a three-word name, which stays a name word, and a single-letter
    connective that reads as an initial instead (P8), which never
    joins.
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
    Both questions asked of a name here and in P8 — how many words
    it has, and whether it is written in one case — are asked of the
    name's OWN words: a maiden marker taken as one, and the words it
    takes (M2), are not among them, and neither is a delimited clause
    (N1, M1). So a clause beside the name changes neither whether the
    connective joins nor how a letter in the name reads, and a letter
    inside such a clause is the clause's word, read by T4 and not by
    P8. The two questions part at one point: a
    marker the pass declines and leaves as a word (M2) is a word, and
    counts toward the three; whether its case is asked is P8's to say.
      "Juan y Eva Garcia"         →  given="Juan y Eva"
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
      "Josep Lluis Carod i III"   →  suffix="i III"
      "Carod y de Rovira i"       →  middle="y"
      "John й Smith"              →  middle="й"
      "É. y É. Smith"             →  given="É."
    The three-word carve-out is about the written FORM, not the word:
    it counts letters, so a symbol connective joins at any length,
    and it reaches every single-letter connective the vocabulary
    holds — Catalan i and Cyrillic и/і/й and Arabic و as well as y
    and e.
    A letter written as a base letter plus a combining mark
    (NFD) that composes to one character is one letter to every
    count here and in P8, and a period-marked initial written that way is one
    initial (#665), so the last two examples above, both typed
    decomposed, read as their composed twins.
    H1 is the counting rule that shows the one-word clause today: a
    title plus the join reads the whole join as the family, where the
    same two words unjoined are two name words and H1 does not fire.
    P1's leading run is the second (#395, landed): its run takes
    the "Vega y Santos" join whole or stops before it.
    Signal: a neighbor: a connective between name words, a single-letter one in a three-word name staying a name word
    history: decisions/P3 · interacts: H1, P1, M2, R1, C3, C4, C6, C7, C10, S6, S10, T4, P8 · implemented: nameparser/_pipeline/_comma.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_post_rules.py
