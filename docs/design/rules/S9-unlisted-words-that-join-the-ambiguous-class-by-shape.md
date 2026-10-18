# S9 — unlisted words that join the ambiguous class by shape

S9. Rationale: no wordlist holds every credential, and a word's
    shape can be written the way a credential is written; but a
    shape is also how some names are written, so it buys the
    ambiguous reading, never the unambiguous one.
    An unlisted word joins the ambiguous class (S4) by SHAPE where
    the caller asks for it. Two or more period-separated chunks is
    one such shape, admitted by default (S3); an unlisted all-caps
    alphabetic word of two or more letters, standing in a suffix
    position of a mixed-case name and belonging to no wordlist, is
    the other. By default that second shape is admitted in one
    position only, the part after a comma with two or more name
    words before it (C1): French and Korean records write the
    SURNAME in capitals, and that convention puts the capitals at
    the end of a name or before a comma, never after a comma behind
    a full name. Everywhere else it is admitted only under the
    caller setting the example lines below name, being a surname
    there as often as a credential, which only the caller can know;
    the cost of that setting is that a three-word name gives up its
    family name to the acronym, while a two-word name keeps it —
    there are no words to spare there, so the class is considered
    and declined and only the fork is reported. The dotted shape does not take every promise of the
    class with it: at the first slot after a comma, C1 reads paired
    initials as the given name unless something speaks for them, and
    makes a flip to the credential run in which no listed member takes
    part in silence, unless paired initials speak only for each
    other.
      "John Smith XYZ"            →  family="XYZ"  · boundary
      "John Smith XYZ"  unlisted_caps_suffixes-everywhere  →  suffix="XYZ"
      "Jean DUPONT"  unlisted_caps_suffixes-everywhere  →  family="DUPONT"  · boundary
      "Jean Pierre DUPONT"  unlisted_caps_suffixes-everywhere  →  suffix="DUPONT"
      "Jean Pierre DUPONT"  unlisted_caps_suffixes-everywhere  →  family="Pierre"
    history: decisions/S9 · interacts: C1, S3, S4 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_classify.py
