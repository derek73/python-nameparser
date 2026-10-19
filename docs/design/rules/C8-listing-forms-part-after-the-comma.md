# C8 — the listing form's part after the comma

C8. Rationale: a comma fixes a family boundary only where a name
    word stands after it to be the given name; a part of titles and
    suffixes alone names nobody.
    In the listing form the part after the
    comma is still read for what it is: a part that is nothing but
    suffix words is the credential run and reads as suffixes, whole
    — the slot after a family comma is postnominal position, so the
    vocabulary's verdict comes before any title reading of the same
    word — and a part that holds no name word at all, titles and suffixes
    only, fixes no family boundary, so a part before the comma with
    more than one name word keeps its positional read, order and
    all. A name word in the part after the comma makes it the
    given name, with titles before it and suffixes after, unless a
    credential opens the part. A credential opening the part makes it
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
      "Smith, PhD"                →  suffix="PhD"
      "Smith, Jr."                →  suffix="Jr."
      "Smith, Sr."                →  suffix="Sr."
      "Smith, PSM I."  strict-comma-suffixes  →  suffix="PSM I."
      "Smith, Ph. D. Jr."         →  suffix="Ph. D. Jr."
      "Smith, MD PhD"             →  suffix="MD PhD"
      "Smith, Dr."                →  title="Dr."
      "Smith, Dr. Jr."            →  suffix="Jr."
      "John Smith, PhD Jones"     →  given="John"
      "John Smith, PhD Jones"     →  suffix="PhD Jones"
      "Doe, PhD Jones"            →  suffix="PhD Jones"
      "John Smith, Ph. D. Jones"  →  suffix="Ph. D. Jones"
      "Steven Hardman, RN - CRNA" →  given="Steven"
      "John Smith, MD Jones"      →  given="Jones"  · boundary
      "Smith, Ms Jane"            →  title="Ms"  · boundary
      "John Smith, Mr."           →  given="John"
      "John Smith, Mr."           →  family="Smith"
      "John Smith, Mr. Jr."       →  given="John"
      "Smith Jr., Mr."            →  family="Smith"  · boundary
    Accepted: a word of both the title and the unambiguous suffix
    vocabulary reads as the postnominal after a family comma in
    every spelling, the honorific's too — position decides for the
    duals, and the slot is postnominal.
      "Smith, Ms."                →  suffix="Ms."
      "Smith, Ms. Jane"           →  title="Ms."
    history: decisions/C8 · interacts: C1, C7, C9, C11, H1, H2, H6, S8, C12 · implemented: nameparser/_pipeline/_comma.py
