# S2 — a suffix word ends a name and never opens the string

S2. Rationale: generational suffixes and credentials are recognized
    by vocabulary; an acronym that is also an ordinary name is only
    unmistakably a credential when its periods are written.
    A suffix never OPENS THE STRING: position outranks the
    vocabulary match, so a suffix-shaped word written before anything
    else reads as whatever its position and shape make it — a title
    where it wears the abbreviation shape (H2), an ordinary name word
    otherwise — and never as a credential belonging to a name that
    has not been written yet. The string, not the name: a title, a
    nickname or a bracketed clause standing first leaves the
    credential reading intact, which is the ONE place this document
    says "opening" and does not mean what P4 and the H Background
    mean by it. A family comma is the other boundary: the comma has
    already named the family, so a credential run may open the part
    after it (C1), and the part before it is that family, less a
    title run opening it (H6).
    A trailing word of the suffix vocabulary reads as a suffix —
    generational forms and credential acronyms alike, and an
    ambiguous acronym written with its periods, one after each
    letter or one after each of two or more letter chunks, counts
    unambiguously; a single trailing period is the abbreviation
    shape any word can wear and does not. The run at a name's
    trailing slot is read ONCE, once the connectives have joined (P3)
    and before the particle chain (P2) and the bound given-name join
    (P5) are made, counting a particle run and the name words the
    chain will take with it as the one name word it will make of
    them — the words both particles and suffix vocabulary standing
    straight behind a particle among them, while a word the reading
    weighs counts as a word of its own wherever it stands; inside a
    credential run a word stands on its own, a title word there still
    a title — and neither join reaches a word the run took. A bare
    ambiguous acronym in that run is read by S4, S5, S6 and S7, and a
    credential with more name text behind it by S8.
      "John Smith Jr."            →  suffix="Jr."
      "Antonio Pavlović mlađi"    →  family="Pavlović"
      "Antonio Pavlović mlađi"    →  suffix="mlađi"
      "Агриппина Младшая"         →  suffix="Младшая"
      "جورج بوش الابن"            →  suffix="الابن"
      "ロバート・ダウニー・ジュニア"  →  suffix="ジュニア"
      "佐藤恵子 国会議員"         →  suffix="国会議員"
      "陳子媚 二世"               →  suffix="二世"
      "Питер Брейгель мл."        →  suffix="мл."
      "Marie Fils"                →  family="Fils"  · boundary
      "Jiří Dienstbier ml."       →  family="ml."  · boundary
      "Pavlović, Antonio mlađi"   →  suffix="mlađi"
      "Stariji Bruegel"           →  given="Stariji"  · boundary
      "John Smith M.A."           →  suffix="M.A."
      "Wang M.Eng."               →  suffix="M.Eng."
      "John Smith PhD"            →  suffix="PhD"
      "Jack Ma."                  →  family="Ma."  · boundary
      "Ph. D. Van Johnson"        →  family="Van Johnson"
      "Ph. D. Van Johnson"        →  title="Ph."
      "Smith, Ph. D. Jr."         →  suffix="Ph. D. Jr."
      "II Van Johnson"            →  given="II"  · boundary
      "Sir Ph. D. Van Johnson"    →  suffix="Ph. D."  · boundary
      "Ph. D., John"              →  family="Ph. D."  · boundary
    Accepted: a title before the credential keeps it a credential,
    and the name loses its surname exactly as it did before this
    clause — `Sir Ph. D. Van Johnson` reads given `Van Johnson` with
    an empty family. That is 1.4.0's reading, and the clause cannot
    reach it: the first piece of the NAME is not computable before
    this decision, since the abbreviation test H2 uses is true of
    `Ph.` itself, so a scan that stepped over titles would step over
    the very piece being judged.
    Accepted: an unambiguous suffix is consumed even when that
    leaves no family name at all.
      "Smith Jr."                 →  family=""
    Accepted: the title chain no longer takes the word this rule
    needs, and the argument a descriptive note here asked for is
    made. A title run leaves one NAME word standing and a
    post-nominal cannot be it (H3, decided 2026-09-08), so `Dr King
    Jr` reads family `King`, suffix `Jr` exactly as this rule
    states, where it read title `Dr King`, family `Jr` before —
    `Dr Smith Jr`, which always read as stated, was the contrast
    that isolated the cause and now reads like its neighbour rather
    than against it. What the floor cannot reach stays descriptive
    and is small: where the run's whole content is the word given
    back, no title is left to name anybody, so the word stands as
    the name rather than as the family — `Dr Jr` reads given `Dr`,
    suffix `Jr`, reporting `title-or-name` (H4), and `Sir Jr`, the
    spelling this note first named, reads by the same branches —
    given `Sir`, suffix `Jr`, the same kind reported — the run
    being empty by then and no branch reading `vocab:given-title`.
    The vocabulary half is decided
    and unchanged (decisions/v1-xfail-triage: `king` stays a
    title, for the addressing forms).
      "Dr Jr"                     →  suffix="Jr"
    history: decisions/S2 · interacts: H1, H2, H3, H4, H5, H6, C1, S3, S4, S5, S6, S7, S8, P2, P3, P4, P5 · implemented: nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
