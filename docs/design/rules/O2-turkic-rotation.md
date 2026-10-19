# O2 — Turkic rotation

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
    Signal: a neighbor: a standalone patronymic marker ending a name of exactly four name words
    history: decisions/O2 · implemented: nameparser/_pipeline/_post_rules.py

