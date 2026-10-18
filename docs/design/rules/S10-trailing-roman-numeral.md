# S10 — the trailing roman numeral

S10. Rationale: a roman numeral ending a name is its generation,
    but one letter is also how an initial is written, and the
    generation it would name is rare; a name of two words has no
    word to spare for it.
    A roman numeral ending a name written without a comma reads as
    the generation — the numerals the vocabulary lists, and those
    up to X it does not, by their shape alone — unless the word in
    front of it is written as an initial, which makes it a name word
    too; in a name written wholly in one case a bare letter in front
    is written as one. A single letter written with a period is an initial, and a
    numeral past X is a name word. A numeral of one letter needs
    words to spare, as a bare ambiguous acronym does (S4): as the
    second of two name words it is the family name, a title in front
    being no word to spare, and either reading is reported, as
    either reading of an ambiguous acronym is. A numeral read by its
    shape alone reports too; a numeral the vocabulary lists in two
    or more letters is not in question and reports nothing, and a
    letter already reported as read as an initial reports nothing
    new: where a title stands after a marked letter (P3), P3's
    report is the one. Written case
    settles the fork in one way only: a numeral written in lower
    case in a name of mixed case is the generation and reports
    nothing, since nobody writes an initial that way. A name written
    wholly in one case says nothing about any letter in it. The part
    before a suffix comma is read as the same name written without
    the comma (C1); the given part after a family comma is not
    counted, the comma having settled the count there (S5).
      "John Smith V"              →  suffix="V"
      "John Smith V"              →  ambiguities=("suffix-or-name",)
      "John W. Ingram V"          →  suffix="V"
      "John Smith VI"             →  suffix="VI"
      "John Smith VI"             →  ambiguities=("suffix-or-name",)
      "John Smith III"            →  ambiguities=()
      "John III"                  →  suffix="III"
      "John V"                    →  family="V"
      "John V"                    →  ambiguities=("suffix-or-name",)
      "Malcolm X"                 →  family="X"
      "JOHN V"                    →  family="V"
      "Dr Smith V"                →  family="V"
      "John V, Dr."               →  family="V"
      "John Smith vi"             →  ambiguities=()
      "john smith i"              →  ambiguities=("suffix-or-name",)
      "John Smith V."             →  family="V."  · boundary
      "John J. V"                 →  family="V"  · boundary
      "John Smith XI"             →  family="XI"  · boundary
      "john v"                    →  family="v"
      "john smith v"              →  ambiguities=("suffix-or-name",)
      "john i"                    →  family="i"
      "john i"                    →  ambiguities=("suffix-or-name",)
      "john i dr."                →  ambiguities=("conjunction-or-initial",)
      "john j v"                  →  family="v"
    Accepted: a numeral with another suffix word behind it is not
    the last word of the name and is read as any word there is, so a
    one-letter numeral before a credential is the family name.
      "John Smith V PhD"          →  family="V"
    history: decisions/S10 · interacts: S2, S4, S7, C1, P2, P3, M2, H1, H3 · implemented: nameparser/_pipeline/_assign.py, nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
