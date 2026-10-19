# C13 — a credential opening the part after the comma

C13. Rationale: a credential is written after the name it belongs
    to, so one standing first in the part after a family comma says
    the part is that name's postnominals and not its given name; a
    word that is also a title says nothing of the kind, being the
    listing form's title as often as a credential.
    A credential opening the part after a family comma makes it
    the postnominal part however it goes on: where the first suffix
    word of the part, with only titles in front of it, is one that
    starts S8's run, which S8 bounds (the split 'Ph. D.' among them),
    every word after it reads as that run reads, a title word as a
    title and any other word as a suffix, under strict mode too,
    whose veto refuses a word the suffix reading and not the run
    ('Smith, PSM I.'). The comma has then fixed nothing, so a part
    before it holding two or more name words keeps its positional
    read, and a part holding one is the family ('John Smith, PhD
    Jones', 'Doe, PhD Jones'). A word of both the title and the
    suffix vocabulary opens nothing, and nor does a credential behind
    one: in front of a given name it is the listing form's title
    ('Smith, Ms Jane'), and no count of the words before the comma
    tells a surname of two words from a given name and a family name.
      "Smith, PSM I."  strict-comma-suffixes  →  suffix="PSM I."
      "John Smith, PhD Jones"     →  given="John"
      "John Smith, PhD Jones"     →  suffix="PhD Jones"
      "Doe, PhD Jones"            →  suffix="PhD Jones"
      "John Smith, Ph. D. Jones"  →  suffix="Ph. D. Jones"
      "Steven Hardman, RN - CRNA" →  given="Steven"
      "John Smith, MD Jones"      →  given="Jones"  · boundary
      "Smith, Ms Jane"            →  title="Ms"  · boundary
    Signal: a neighbor: a credential opening the part after a family comma
    history: decisions/C13 · interacts: C1, C3, C8, C9, C11, S8, H6 · implemented: nameparser/_pipeline/_comma.py
