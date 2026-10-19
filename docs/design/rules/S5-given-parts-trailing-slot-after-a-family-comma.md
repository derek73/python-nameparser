# S5 — the given part's trailing slot after a family comma

S5. Rationale: a family comma has already named the family and the
    given name, so at the end of the given part the words-to-spare
    count has nothing to say, and only the writing can.
    After a family comma, a member of the ambiguous class (S4)
    ending the GIVEN part is read as the comma-less spelling reads a
    word ending the name, and the count is not what decides it
    there. The comma has already named the family and the first
    name word after it is the given name, so the words to spare are
    there by construction and the count says nothing — unless that
    first word is a never-given particle, which is no given name and
    needs the next name word to attach to (P1): that word is the
    surname the particle heads, not a word to spare, so it reads as
    a name unless its capitals in a mixed-case name say credential,
    as they do with no words to spare anywhere (S6): `SMITH, VD MA`
    reads as `Smith, vd Ma` does, `Smith, de MA` keeps suffix `MA`,
    and `SMITH, VAN MA`, whose particle can be a given name, keeps
    it and reads suffix `MA`. Otherwise a word that ENDS that part
    reads as the credential unless its WRITING says otherwise, and a
    word that does not end it is never asked. "Ending the given
    part" reaches past the credentials behind it and past a trailing
    title, which is transparent to this reading as it is to the rest
    of the trailing reading (H5); a name word behind the word ends
    the reach, and so does a PARTICLE the suffix vocabulary does not
    also claim: it belongs to the family the comma already named and
    is taken there by a rule that runs after this reading is made
    (P6), so `Doe, John MA do` keeps its middle name though the
    capitals would otherwise have taken the word. A particle the
    suffix vocabulary DOES claim is looked past like any other
    credential, so `Doe, John MA vd` reads suffix `MA`, with `vd`
    attaching behind it. Where the reach ends, the word is an
    ordinary middle name, read in silence.
    A particle in FRONT of the word takes it out of this slot as
    well, and takes the word behind it too: where what follows the
    particle reads as a name rather than a credential the two are
    one name, so neither word is asked and neither reports —
    `Doe, John van Ma` reads middle `van Ma` and `Doe, John DO Ed`
    middle `DO Ed`, where `Doe, John van MA` reads suffix `MA` and
    `Doe, John DO` alone reads the credential, both reporting.
    Every word this slot does read reports the fork whichever way it
    went, so a run of members all read as credentials reports once
    for each, as the same words do without the comma — while a
    member the writing keeps as a name stops the reading there, and
    whatever stands in front of it is name text, asked nothing and
    reporting nothing. One member of the class is particle
    vocabulary as well, and where it stands alone at this slot P6
    decides it: the capitals take it as the credential, as does an
    unambiguous credential in front of it (S7), and every other
    spelling attaches to the family, reported there as P6's fork
    rather than as this one. Behind another particle it does not
    stand alone — the two are one particle run by then — and the
    run attaches whatever the capitals say (P6).
      "Doe, John MA"              →  suffix="MA"
      "Doe, John Ma"              →  middle="Ma"  · boundary
      "Doe, John MA Smith"        →  middle="MA Smith"  · boundary
      "Doe, John DO"              →  suffix="DO"
      "SMITH, JOHN DO"            →  family="DO SMITH"  · boundary
      "SMITH, VD MA"              →  family="SMITH VD MA"
      "smith, de ma"              →  family="smith de ma"
      "SMITH, VD DE LA MA"        →  family="SMITH VD DE LA MA"
      "Doe, John MA JD"           →  ambiguities=("suffix-or-name", "suffix-or-name")
      "Doe, John MA Ma"           →  middle="MA Ma"  · boundary
      "Doe, John MA Ma"           →  ambiguities=("suffix-or-name",)  · boundary
      "Doe, John van Ma"          →  middle="van Ma"  · boundary
      "Doe, John van Ma"          →  ambiguities=()  · boundary
      "Doe, John DO Ed"           →  middle="DO Ed"  · boundary
      "Doe, John DO Ed"           →  ambiguities=()  · boundary
    history: decisions/S5 · interacts: C1, C11, H5, P1, P6, S4, S6, S7 · implemented: nameparser/_pipeline/_assign.py
