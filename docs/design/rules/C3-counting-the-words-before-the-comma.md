# C3 — counting the words before the comma

C3. Rationale: the listing form puts a surname before the comma,
    and a particle surname is one surname.
    Wherever the comma's decision (C1) counts the words before the
    comma, a particle
    run and the one name word it attaches to are one word, the reach
    P1's fold counts rather than the whole of P2's chain: the listing
    form puts a surname before the comma, and a particle surname is
    one surname ('De La Cruz, Ed' reads as 'Royce, Ed' does, 'van der
    Berg, PhD' as 'Berg, PhD'). Where that surname is the whole part,
    the comma settles P1's fork for a leading particle that could be
    a given name, being the evidence that the part is a surname; a
    word after the one the particle attaches to is a second word, and
    a suffix word ends the particle's reach. A word that is also
    title vocabulary is not a particle to this count where it opens
    the part, reading there as the title it also is (H1); inside a
    surname it chains ('de St Pierre, Ed' reads given 'Ed'). A
    connective join and a bound given-name pair are not one word
    here: whether P3 joins a connective depends on the words of the
    whole name, which this count is part of deciding, and a bound
    given name builds a given name rather than a surname (P5) — a
    word that is a particle as well counts as the particle ('Abu
    Bakar, Ed' reads given 'Ed'). A title in front is a word to the
    count an unambiguous credential takes, so 'Dr. van der Berg, PhD'
    reads as its part does alone.
      "Ortega y Gasset, Dr."      →  given="Ortega"
      "De La Cruz, M.J. K.L."     →  given="M.J."
      "De La Cruz, Ed"            →  given="Ed"
      "van der Berg, MA"          →  family="van der Berg"
      "van der Berg, MA"          →  suffix="MA"
      "Van Buren, Ed"             →  family="Van Buren"
      "van der Berg, PhD"         →  family="van der Berg"
      "John van Buren, Ed"        →  suffix="Ed"  · boundary
      "Ortega y Gasset, Ed"       →  suffix="Ed"  · boundary
      "abdul Salam, Ed"           →  suffix="Ed"  · boundary
    Accepted: a title in front of a particle surname, before the
    credential class's word, reads the listing form. The surname
    counts once and the title is no name word, so the count reads the
    listing form, and the listing form peels a title before the comma
    (H6) unless the word is a particle too, as 'Freiherr' is, which
    stays in the family. For a German rank that reading is the right one:
    since 1919 a former noble title is part of the legal surname,
    written between the given name and the particle, so 'Freiherr von
    Berg' is the family name in 'Freiherr von Berg, Ed', as 2.0
    through 2.3 read it. Before an unambiguous credential the same
    words keep the title apart ('Freiherr von Berg, PhD'), that count
    taking the title as a word; both are readings of one name.
      "Freiherr von Berg, Ed"     →  family="Freiherr von Berg"
    history: decisions/C3 · interacts: C1, C4, C5, H1, H6, P1, P2, P3, P5, C12 · implemented: nameparser/_pipeline/_comma.py
