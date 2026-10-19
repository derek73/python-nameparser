# O5 — the lone name word's convention, and reporting it

O5. Rationale: O4 reads a name by comparing where its words stand,
    and a name of exactly one name word gives it nothing to compare
    — the first name word is also the last, so the rule that decides
    every longer name is silent here. Nothing in such an input says
    whether the word is a given name or a family name: both readings
    fit it equally well, and the library still has to report one.
    A name of one name word that nothing else has decided reads that
    word as the given name under the default given-first order, and
    as the family name under a declared family-first one. That is a
    convention rather than a determination — the same input has to
    read the same way every time, so one of two equally consistent
    readings is fixed in advance — and it is not evidence about the
    word. Every rule that DOES decide such a name outranks it, and
    each of them carves out a case it declines to decide — where the
    convention is what is left. A title makes the word the family
    name (H1), except a given-name title, which addresses by given
    name; a nickname beside it does the same (N3), except where a
    suffix stands beside them too, which its count does not set
    aside; and a maiden name beside it does the same (M4), except
    where the vocabulary or the word's own shape has claimed the
    word already. The convention is reported: a name whose one name
    word nothing else decided carries a `given-or-family` ambiguity
    naming the field the convention chose. The report is exactly as
    narrow as the convention, so every rule named above silences it
    where it fires, a family comma — a comma with a name segment
    after it — silences it, a script whose own convention settles
    the order (W4) silences it, and so does the word's own claim — a
    particle, a bound given name, an initial (T5, T4). A comma with
    nothing after it names no family and silences nothing, so
    `سلمان،` and `Smith,` report where `Smith, Andrew` does not. A
    comma with only a TITLE after it names no family either, but the
    title still decides the field wherever it stands, so `John III, Dr.`
    is silent for H1's reason and not the comma's. A word with no
    letter or digit in it is no name word and
    reports nothing (A2). Where the one name unit carries title
    vocabulary in a word beside the one it places, or is itself title
    vocabulary left standing by the title peel, the doubt reported is `title-or-name`
    instead, which H4 states — so a title silences THIS kind, not
    every report at the site.
      "Smith"                     →  given="Smith"
      "Garcia"  family-first      →  family="Garcia"
      "Sir John"                  →  given="John"
      "'Smitty' Jones Jr."        →  given="Jones"
      "abd née Jones"             →  given="abd"
      "Mr. Johnson"               →  family="Johnson"  · boundary
      "'Smitty' Jones"            →  family="Jones"  · boundary
      "Smith née Jones"           →  family="Smith"  · boundary
      "Andrew"                    →  ambiguities=("given-or-family",)
      "Garcia"  family-first      →  ambiguities=("given-or-family",)
      "Juan & Garcia"             →  ambiguities=("given-or-family",)
      "'Smitty' Jones Jr."        →  ambiguities=("given-or-family",)
      "Smith Jr."                 →  ambiguities=("given-or-family",)
      "Dr. Smith"                 →  ambiguities=()  · boundary
      "Sir John"                  →  ambiguities=()
      "Smith née Jones"           →  ambiguities=()
      "abd née Jones"             →  ambiguities=()
      "j"                         →  ambiguities=()
    Signal: a count: one name word that nothing else decided
    history: decisions/O5 · interacts: O4, H1, N3, M4, H4, W4, P3, A2, T4, T5 · implemented: nameparser/_pipeline/_assign.py

