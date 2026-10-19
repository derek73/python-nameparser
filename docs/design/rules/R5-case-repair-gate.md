# R5 — the case-repair gate

R5. Rationale: mixed case is evidence that the writer cased the name
    deliberately, and a repair cannot tell a deliberate spelling from
    a mistaken one. A name written wholly in one case leaves the
    repair no such evidence to read either way — the writer who
    always writes lowercase is indistinguishable from the writer who
    could not be bothered — so repair proceeds there, which is a
    choice about how to act absent evidence rather than a claim that
    nothing can be lost by it.
    Case repair acts only on a name written entirely in one case.
    The suffixes are left out of that test: a suffix says nothing
    about how the writer cased the name — III, PhD, Jr. are written
    that way whatever the name's case — so the test reads every word
    the parse did not put in the suffix role. A title is not left
    out, and a cased title still holds repair back. A name whose
    words outside the suffix are written in more than one case is
    kept as it was written, and whether that casing is right does
    not enter into it, unless repair was asked for anyway. The same
    test is then asked of each suffix on its own: a suffix written
    in more than one case is the writer's spelling and is kept as
    written where repair was not forced; one written in a single
    case is repaired like any other.
      "juan mcdonald"             →  capitalized="Juan McDonald"
      "SHIRLEY MACLAINE"          →  capitalized="Shirley MacLaine"
      "Shirley Maclaine"          →  capitalized="Shirley Maclaine"
      "Shirley Maclaine"          →  capitalized_forced="Shirley MacLaine"  · boundary
      "juan garcia III"           →  capitalized="Juan Garcia III"
      "juan garcia PhD"           →  capitalized="Juan Garcia PhD"
      "JUAN GARCIA Jr."           →  capitalized="Juan Garcia Jr."
      "dr. juan garcia III"       →  capitalized="Dr. Juan Garcia III"
      "Dr. juan garcia"           →  capitalized="Dr. juan garcia"  · boundary
      "Juan garcia III"           →  capitalized="Juan garcia III"  · boundary
      "john smith EdD"            →  capitalized="John Smith EdD"
      "juan garcia Iii"           →  capitalized="Juan Garcia Iii"  · boundary
      "john smith EdD"            →  capitalized_forced="John Smith EDD"
    Signal: a case contrast: whether the words outside the suffix are written in one case
    history: decisions/R5 · interacts: R4, P3, S6 · implemented: nameparser/_render.py

