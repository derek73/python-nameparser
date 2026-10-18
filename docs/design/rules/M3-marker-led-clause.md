# M3 — the marker-led clause

M3. Rationale: an enclosure says nothing about whether it means
    maiden, but a recognized marker word inside it does — the clause
    announces itself, so the caller does not have to declare the
    pair.
    A bracketed clause whose content opens with a recognized marker
    and carries a word after it reads as the maiden name,
    whichever bucket the enclosing pair sits in — unless the content
    is suffix-shaped, which S1 takes first — the marker itself
    dropped, as M1 drops it. A marker with no word after it is just
    a word in brackets, and so is a marker no separator divides from
    the name, the fullwidth-colon spelling M2 records. And a marker
    followed by a comma is no marker, whether the comma stands alone
    or is glued to either word — here and in M1's drop alike, so a
    clause the caller declared maiden keeps that marker. Where the
    pair is already configured for maiden names M1 governs and this
    adds nothing. Being keyed on the content rather than on the
    pair, this reaches a nickname pair's clause too, and M1's
    independence then governs what it produces: where a marker-led
    clause stands beside another marker-led clause, both read as
    maiden and join into one maiden name, leaving no nickname.
      "Jane Smith (née Jones)"    →  maiden="Jones"
      "Jane (née Jones) Smith"    →  family="Smith"
      "Jane Smith (née Jr.)"      →  suffix="Jr."
      "Jane Smith (née)"          →  nickname="née"  · boundary
      "Maria Kowalska (z domu Nowak)"  →  maiden="Nowak"
      "Maria Kowalska (z domu)"   →  nickname="z domu"  · boundary
      "Jane (née , Jones) Smith"  →  nickname="née , Jones"  · boundary
      "Jane (née ,Jones) Smith"  maiden-parens  →  maiden="née ,Jones"  · boundary
    Accepted: the word taken after the marker is not tested for
    being a name word, so unlike M2's bare take this one does not
    stop at a suffix word — the same two words read one way
    bracketed and another way bare. This does not contradict the
    S1 example above: S1 asks whether the WHOLE clause is
    suffix-shaped, which the trailing period makes true of the one
    and false of the other, so only the V clause reaches this rule.
      "Jane Smith (née V)"        →  maiden="V"
    history: decisions.md#M3 · interacts: M1, M2, S1, N1 · implemented: nameparser/_pipeline/_extract.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_vocab.py

