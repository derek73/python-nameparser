# R1 — fields are views of the parsed words

R1. Rationale: a field is a way of reading the parse, not a stored
    string.
    Every field is a view computed from the parsed words at read
    time, joining its words in written order — except folded family
    words — O3's fold and, since #379, P6's attached tussenvoegsel —
    which render before the rest of the family wherever they stood in
    the string.
    Words are separated as the writer separated them. The suffix view
    is the one place this is visible, because it is the only field
    that can hold parts the writer comma-separated: a run of
    post-nominals written with spaces renders with spaces, and one
    written with commas keeps them. The separator is the comma the
    writer typed, read off the words' positions once their roles are
    known; a delimiter the configuration names is a separator too,
    and so is any name word standing between two post-nominals.
      "Dr. Juan Q. Xavier de la Vega III"  →  family="de la Vega"
      "Hassan, Mohamad Ahmad Ali"  middle_as_family  →  family="Ahmad Ali Hassan"
      "Hassan, Mohamad Ahmad Ali"          →  family="Hassan"  · boundary
      "Smith, MD PhD"                      →  suffix="MD PhD"
      "John Smith MD PhD"                  →  suffix="MD PhD"
      "John Smith, MD, Bart"               →  suffix="MD, Bart"
      "Smith, John, PhD - i Soler" extra_suffix_delimiters-dash →  suffix="PhD, i Soler"
    Accepted: a suffix value handed to revise() derives its entries the
    same way, from the value's own commas, so a name's rendered suffix
    revises back to itself wherever the value's words read as the
    whole name read them — a glued CJK honorific peels off an initial
    in a bare value where the whole name kept it glued, one corpus
    name of the 372 with a suffix (decisions/R1, 2026-09-06, which
    counted 368 of 1117 then; re-measured 2026-09-10 with this
    bundle's rows in the corpora, 372 of 1156 distinct names and the
    same single failure). A delimiter the configuration names parts a
    value only where the value's own words, read as a name, give it a
    tail segment for the core to be dropped on; a run of post-nominals
    has none, with or without a comma of its own, so there the
    delimiter stays a word of the run — write a comma at the boundary
    instead. Stated without an example line because every line here
    names an input string, and this shape needs a field revised after
    the parse.
    history: decisions/R1 · interacts: O3, P3, P6, R3, M2 · implemented: nameparser/_parser.py, nameparser/_pipeline/_post_rules.py, nameparser/_types.py

