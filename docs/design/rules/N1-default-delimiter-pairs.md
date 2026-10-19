# N1 — the default delimiter pairs

N1. Rationale: a quoted or bracketed clause beside a name is an
    informal alias, not part of the name.
    A clause enclosed by a configured nickname delimiter pair reads
    as the nickname and is lifted out of the name, a comma inside it
    kept as written — the comma divides nothing there, though the
    dots T2 and T3 name still divide a clause as they divide a name;
    an empty enclosure is simply dropped.
      "Andrew (Andy) Perkins"     →  nickname="Andy"
      "Jane (Janey, Jo) Smith"    →  nickname="Janey, Jo"
      "Jean 'JD' Smith"           →  nickname="JD"
      "Anna () Smith"             →  nickname=""  · boundary
      "John ｢Jack｣ Smith"         →  nickname="Jack"
    Signal: a neighbor: a configured nickname delimiter pair enclosing a clause
    history: decisions/N1 · interacts: T2, T3 · implemented: nameparser/_pipeline/_extract.py, nameparser/_pipeline/_tokenize.py

