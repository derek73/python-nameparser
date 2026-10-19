# C12 — a suffix word ending the name before the comma

C12. Rationale: a generation belongs to the name it ends, so a name
    written in natural order carries it before the comma and its
    credentials after ('John J Ingram III, MD'), as it does Esq. or a
    post-nominal honorific; a listing whose surname takes a
    generation puts it there too, but a given name follows it, and a
    given name is written as a name.
    Where the part before the first comma ends in a suffix word — a
    generation such as Jr. or II, Esq., or an honorific such as
    Rinpoche, not an acronym — or in a roman numeral the trailing
    fork reads as the generation (S10), the words in front of it are
    a whole name (C3's count, in which a title in front is a word,
    but for a one-letter numeral, which S10 counts without it), and
    the
    name carries the case contrast C6 asks for, the part after the
    comma is the credential run and the comma a suffix comma, a title
    word in it reading as a title and any other word, a title and
    suffix dual among them, as a suffix; a
    word of it written as a name, or an initial, keeps the listing
    form.
      "John Smith II, AD"         →  given="John"
      "John Smith II, AD"         →  suffix="II, AD"
      "John Smith Jr., þingmaður" →  suffix="Jr., þingmaður"
      "John Smith Jr., MBChB PhD" →  suffix="Jr., MBChB PhD"
      "John Smith VI, AD"         →  suffix="VI, AD"
      "John Smith V, AD"          →  suffix="V, AD"
      "John Smith Jr., AD MD"     →  suffix="Jr., AD MD"
      "John Smith Jr., Sir AD"    →  title="Sir"
      "John Smith Jr., Sir AD"    →  suffix="Jr., AD"
      "John Smith II, AD"         →  capitalized_forced="John Smith II, AD"
      "John Smith II, AD"         →  ambiguities=("suffix-or-name",)
      "Lloret Palol II, Josep Antoni"  →  given="Josep"  · boundary
      "Garcia Lopez Jr., Juan"    →  given="Juan"  · boundary
      "John Smith Jr., J."        →  given="J."  · boundary
      "Smith Jr., John"           →  given="John"  · boundary
      "Jane nee Smith Jr., AD"    →  given="AD"  · boundary
      "Smith Jones Jr., J.A."     →  given="J.A."  · boundary
      "Dr. Smith Jr., AD"         →  suffix="Jr., AD"
      "Smith VI, AD"              →  given="AD"  · boundary
      "Smith V, AD"               →  given="AD"  · boundary
      "Dr. Smith V, AD"           →  given="AD"  · boundary
      "VI, AD"                    →  given="AD"  · boundary
      "John J VI, AD"             →  given="AD"  · boundary
      "John Smith, AD"            →  given="AD"  · boundary
      "JOHN SMITH JR, AD"         →  given="AD"  · boundary
    Accepted: initials written without periods after the generation
    read as the credential they look like, a word of two capitals
    being both; written with them they are initials, as C5 reads
    them. A name written in one case, or in a script without
    case, has no contrast to read and keeps the listing form, as C6's
    unlisted all-caps word does.
      "Lloret Palol II, JA"       →  suffix="II, JA"
    history: decisions/C12 · interacts: C1, C3, C6, C8, C11, S10 · implemented: nameparser/_pipeline/_comma.py
