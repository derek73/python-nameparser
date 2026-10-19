# H6 — a title before a family comma

H6. Rationale: the listing form moves the surname to the front and
    leaves everything else where it was written, so a title written
    ahead of the name ends up ahead of the surname — `Dr. Smith,
    John` is `Dr. John Smith` indexed. The comma names the family,
    and a title is no part of it. But the slot in front of a family
    comma is a surname's slot as well, and a surname can open with
    an abbreviated word (Sta. Maria, Sto. Domingo), so only the
    vocabulary claims a word there, never H2's shape, and a word
    that is a particle as well as a title opens a surname rather
    than ranking a person.
    A run of title words opening the part before a family comma is
    the title, joining the title field in input order with any title
    after the comma. The run admits a title word only as vocabulary
    knows it, stops at a word that is also a particle, or where
    nothing but post-nominals stands behind it (H3), and always
    leaves the family at least one word. The comma decides the
    family whatever
    the order declared, so the reading is the same under every
    name_order.
      "Dr. Smith, John"           →  title="Dr."
      "Dr. Smith, John"           →  family="Smith"
      "Prof. Dr. Brühl, Ada"      →  title="Prof. Dr."
      "Dr. de la Vega, Juan"      →  family="de la Vega"
      "Sir Smith, John"           →  given="John"
      "Prof. Smith, Dr. John"     →  title="Prof. Dr."
      "Rev. Sr. Smith, Mary"      →  title="Rev. Sr."
      "Dr. Mc Donald, John"       →  family="Mc Donald"
      "Prof. Smith, John, PhD"    →  family="Smith"
      "Dr., John"                 →  family="Dr."  · boundary
      "Dr. King, John"            →  family="King"  · boundary
      "Sta. Maria, Juan"          →  family="Sta. Maria"  · boundary
      "MD PhD Jr., John"          →  family="MD"  · boundary
      "St Pierre, Ed"             →  family="St Pierre"  · boundary
      "Dr. St. Pierre, Ed"        →  family="St. Pierre"  · boundary
    Accepted: a title word that is also an ordinary surname (king,
    judge, bishop, greve) opening a surname of two words is read as
    the title, as it is in front of a name with no comma (H1). A
    double-barrelled surname that begins with such a word loses it.
      "King Smith, John"          →  title="King"
    Accepted: what keeps a word in the family is the particle stop
    and nothing else. 'Freiherr' and 'St' are particles as well as
    titles, so they stay in either spelling, keeping 'St Pierre'
    whole and 'Freiherr von Berg' as C3 reads it. The other German
    ranks are titles only, so they peel, though since 1919 a rank
    is part of the legal surname for all of them alike; that is the
    vocabulary's distinction, not this rule's. A title in front of
    a particle still peels.
      "Graf Lambsdorff, Otto"     →  title="Graf"
      "Freiherr von Berg, Ed"     →  family="Freiherr von Berg"
      "Dr. Freiherr von Berg, Ed" →  title="Dr."
    Signal: a neighbor: title vocabulary opening the part before a family comma
    history: decisions/H6 · interacts: C1, C3, H1, H2, H3, M2, P1, P2, P4, S2, W3 · implemented: nameparser/_pipeline/_assign.py

