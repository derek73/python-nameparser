# S8 — the credential's trailing run

S8. Rationale: a credential is the writer's mark that the
    post-nominals have begun, so what follows it in its part is
    post-nominal too.
    A credential after the name core starts a run to the end of its
    part (#602). An unambiguous suffix word of two or more letters,
    in any script, standing after two name words where no comma divides
    the name or before a suffix comma, or after the given word in
    the part after a family comma, makes every later word of that
    part a suffix, except a title word, which reads as a title, and
    in that given part the particles ending it, behind any
    post-nominals, which P6 attaches to the family — other than a
    lone member of the ambiguous class, which reads as the
    credential. A lone particle is
    not a name word for the count, 'de Mesnil' being one surname,
    unless the credential stands right behind it, leaving it nothing
    to join: then it counts as a name word of its own ('John von PhD
    Jones'). A
    particle run with the words the chain joins to it is one name
    word, 'der la' and 'la Smith Secretary' each counting once (P2).
    A title word
    never starts the run, and neither does a member of the ambiguous
    class, a single letter, a connective, a word that is also
    particle or bound given-name vocabulary: a credential is the
    writer's mark that the post-nominals have begun, and those carry
    no such mark. An honorific or a generational word carries it as
    a credential does, whatever its script. A name word the run
    absorbs is reported `suffix-or-name`.
      "John Smith PhD Jones"      →  suffix="PhD Jones"
      "John Smith PhD Jones"      →  ambiguities=("suffix-or-name",)
      "Eric H. Holder Jr. Attorney General"  →  title="Attorney General"
      "John Smith PhD Prof. Ma"   →  suffix="PhD Ma"
      "Smith, John PhD Jones"     →  suffix="PhD Jones"
      "John von PhD Jones"        →  family="von"
      "John von PhD Jones"        →  suffix="PhD Jones"
      "Smith, John PhD de Jr."    →  family="de Smith"  · boundary
      "Mary Jane King Smith"      →  family="Smith"
      "Josep Carod i Rovira"      →  family="Carod i Rovira"
      "Mohamed Ali Abd Allah"     →  family="Allah"
      "Antonio Pavlović mlađi Jones"  →  suffix="mlađi Jones"
      "Pieter Bruegel stariji Jones"  →  suffix="stariji Jones"
      "Ана Хорват старији Џонс"   →  suffix="старији Џонс"
      "Гай Плиний Старший Иванов"  →  suffix="Старший Иванов"
      "राम शर्मा साहब मोहन"          →  suffix="साहब मोहन"
      "राम शर्मा साहब मोहन"          →  ambiguities=("suffix-or-name",)
      "John PhD Smith"            →  family="Smith"  · boundary
    history: decisions/S2 · interacts: H5, M2, P2, P3, P5, P6, S2, S4, S7, C1 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_pieces.py
