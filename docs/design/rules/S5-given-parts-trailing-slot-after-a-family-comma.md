# S5 — the given part's trailing slot after a family comma

**When:** a member of the ambiguous class (S4) stands in the GIVEN part after a family comma, as in "Doe, John MA".

**Then:** after a family comma, a member of the ambiguous class (S4) ending the GIVEN part is read as the comma-less spelling reads a word ending the name, and the count is not what decides it there.

- **A generation word that is also a name (S11) is a member here too**: an agnomen's writing never keeps it a name, and a generation word's Title case does, as S6 reads it.
  ```
  "Alves, Pedro Neto"         →  suffix="Neto"
  "Alves, Pedro Fils"         →  middle="Fils"  · boundary
  ```
- **In the given part, the writing decides**: the comma has already named the family and the first name word after it is the given name, so the words to spare are there by construction and the count says nothing; a word that ENDS that part reads as the credential unless its WRITING says otherwise, and a word that does not end it is never asked.
  ```
  "Doe, John MA"              →  suffix="MA"
  "Doe, John DO"              →  suffix="DO"
  "Doe, John Ma"              →  middle="Ma"  · boundary
  ```
- **How far "ending the given part" reaches.** It reaches past the credentials behind it and past a trailing title, which is transparent to this reading as it is to the rest of the trailing reading (H5); a name word behind the word ends the reach, and so does a PARTICLE the suffix vocabulary does not also claim as an unambiguous suffix word (`do` is in its ambiguous half): it belongs to the family the comma already named and is taken there by a rule that runs after this reading is made (P6), so `Doe, John Ed do` keeps its middle name. A word its capitals settle in a name of mixed case is not reached that way: it starts the credential's run, which reads every word behind it as a suffix (S8), so `Doe, John MA Smith` and `Doe, John MA do` read as `Doe, John PhD Smith` and `Doe, John PhD do` do. A particle the suffix vocabulary DOES claim is looked past like any other credential, so `Doe, John MA vd` reads suffix `MA`, with `vd` attaching behind it. Where the reach ends, the word is an ordinary middle name, read in silence.
  ```
  "Doe, John Ma Smith"        →  middle="Ma Smith"  · boundary
  "Doe, John MA Smith"        →  suffix="MA Smith"
  "Doe, John MA do"           →  suffix="MA do"
  ```
- **What reports.** Every word this slot does read reports the fork whichever way it went, unless its capitals settled it (S6), so a run of members all read as credentials reports once for each, as the same words do without the comma — while a member the writing keeps as a name stops the reading there, and whatever stands in front of it is name text, asked nothing and reporting nothing.
  ```
  "DOE, JOHN MA JD"           →  ambiguities=("suffix-or-name", "suffix-or-name")
  "Doe, John MA JD"           →  ambiguities=()
  "Doe, John ma Ma"           →  middle="ma Ma"  · boundary
  "Doe, John ma Ma"           →  ambiguities=("suffix-or-name",)  · boundary
  ```

**Because:** a family comma has already named the family and the given name, so at the end of the given part the words-to-spare count has nothing to say, and only the writing can.

**Except:**

- **The first word after the comma is a never-given particle**, which is no given name and needs the next name word to attach to (P1): that word is the surname the particle heads, not a word to spare, so it reads as a name unless its capitals in a mixed-case name say credential, as they do with no words to spare anywhere (S6): `SMITH, VD MA` reads as `Smith, vd Ma` does, `Smith, de MA` keeps suffix `MA`, and `SMITH, VAN MA`, whose particle can be a given name, keeps it and reads suffix `MA`.
  ```
  "SMITH, VD MA"              →  family="SMITH VD MA"
  "smith, de ma"              →  family="smith de ma"
  "SMITH, VD DE LA MA"        →  family="SMITH VD DE LA MA"
  ```
- **A particle in FRONT of the word** takes it out of this slot as well, and takes the word behind it too: where what follows the particle reads as a name rather than a credential the two are one name, so neither word is asked and neither reports — `Doe, John van Ma` reads middle `van Ma` and `Doe, John DO Ed` middle `DO Ed`, where `Doe, John van MA` reads suffix `MA` and `Doe, John DO` alone reads the credential, both settled by their capitals (S6).
  ```
  "Doe, John van Ma"          →  middle="van Ma"  · boundary
  "Doe, John van Ma"          →  ambiguities=()  · boundary
  "Doe, John DO Ed"           →  middle="DO Ed"  · boundary
  "Doe, John DO Ed"           →  ambiguities=()  · boundary
  ```

**Precedence:**

- **The member of the class that is particle vocabulary as well, standing alone at this slot** ("Doe, John Do"): P6 decides it: the capitals take it as the credential, as does an unambiguous credential in front of it (S7), and every other spelling attaches to the family, reported there as P6's fork rather than as this one. Behind another particle it does not stand alone — the two are one particle run by then — and the run attaches whatever the capitals say (P6).
  ```
  "SMITH, JOHN DO"            →  family="DO SMITH"  · boundary
  ```

---
**Signal:** position: the word ending the given part after a family comma
**history:** decisions/S5 · **implemented:** nameparser/_pipeline/_assign.py
