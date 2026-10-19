# M4 — a maiden marker makes the lone name word the family

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
      "j nee smith"               →  given="j"  · boundary
    Signal: a count: one name word left beside a maiden name
    history: decisions/M4 · interacts: M1, M2, M3, H1, N3, O5, T4, T5 · implemented: nameparser/_pipeline/_post_rules.py

