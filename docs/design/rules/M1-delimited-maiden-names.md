# M1 — delimited maiden names

M1. Rationale: an enclosure the caller has declared to mean maiden
    holds the former family name; a recognized marker word inside it
    marks the clause and is not itself part of the name.
    With a delimiter pair configured for maiden names, its enclosed
    clause reads as the maiden name — unless the content is
    suffix-shaped, which S1 takes first — a leading recognized
    marker being dropped where the clause holds a word past it; a
    clause of nothing but its marker keeps its words, which may
    themselves be a surname (Nee).
    Clauses are independent: two enclosures read as one maiden name,
    each dropping or keeping its own marker. A pair configured for
    both maiden and nickname reads maiden. Configuring the pair is
    what this rule needs for a clause that does not announce itself
    — markerless content, and a lone marker alike, whether that
    marker is one word or several; a clause holding a word past its
    marker reads as the maiden name inside a nickname pair as well
    (M3), the suffix-shaped content S1 takes excepted there as it is
    here.
      "Jane Smith (née Jones)"  maiden-parens  →  maiden="Jones"
      "Jane Smith (Nee)"  maiden-parens        →  maiden="Nee"  · boundary
      "Jane Smith (Nee) (Jones)"  maiden-parens  →  maiden="Nee Jones"
      "Andrew Perkins (MBA)"  maiden-parens  →  suffix="MBA"  · boundary
      "Maria Kowalska (z domu)"  maiden-parens  →  maiden="z domu"  · boundary
      "Maria Kowalska (z, domu Nowak)"  maiden-parens  →  maiden="z, domu Nowak"  · boundary
    Signal: a neighbor: a configured maiden delimiter pair enclosing a clause
    history: decisions/M1 · interacts: S1, M2, M3, M4 · implemented: nameparser/_pipeline/_extract.py, nameparser/_pipeline/_group.py

