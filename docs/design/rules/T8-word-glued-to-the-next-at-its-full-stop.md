# T8 — a word glued to the next at its full stop

**When:** a word of the part before any comma is glued to the next at its full stop, a chunk the parser reads on its own before the stop and a name after it, as in "Dr.John Smith" or "Ц.Сандаг-Очир".

**Then:** the word reads as it does with a space there: the chunk keeps its full stop and is read as it is read written apart, and the name after it is a word of its own.

- **A chunk the parser reads on its own** is one letter in a script with case, a transliteration digraph H2 names, a listed title that is no saint particle, or a listed given name written short. A run of single letters before the name stays one chunk, as T7 keeps it; titles glued to each other divide at each stop, as they read written apart, and so do a digraph and the initials behind it.
  ```
  "Dr.John Smith"             →  title="Dr."
  "Dr.John Smith"             →  given="John"
  "Ц.Сандаг-Очир"             →  family="Сандаг-Очир"
  "Ahmed Ali M.Hassan"        →  family="Hassan"
  "Yu.A.Chibrikova"           →  family="Chibrikova"
  "J.R.Smith"                 →  given_names="J.R."
  "Lt.Gov.John Smith"         →  title="Lt.Gov."
  "Maj.Gen.John Smith"        →  title="Maj.Gen."
  "Ma.Refugio Torres Vitela"  →  given="Ma."
  "Dr.Smith"                  →  family="Smith"
  "Dr.J. Smith"               →  given="J."
  ```
- **The name after the stop** is a word of letters, apostrophes and hyphens whose first letter with case is not lower case, is not closed by a full stop of its own, and is no unambiguous title or credential; a name that is also a credential divides as its spaced writing reads. A name has to close the word: initials alone behind a letter or a digraph stay one word, as initials ('Kim Yu.A.'), though behind a title they divide ('Dr.J. Smith').
  ```
  "Dr.McDonald Jones"         →  title="Dr."
  "Mr.Ed Smith"               →  given="Ed"
  "Kim Yu.A."                 →  family="Yu.A."
  "Gülcan B.TURAN"            →  family="TURAN"
  "Dr.J.R. Smith"             →  title="Dr."
  ```
- **The rendering keeps the word as it was written**, the pieces joining with nothing between them where they stand side by side (R1).
  ```
  "Dr.John Smith"             →  str="Dr.John Smith"
  ```

- **Initials cut from the last name word of a part, behind a word that is no unambiguous title, are reported**, the credential S3 read the whole as by its shape being the reading not taken, post-nominals after the word, or a suffix comma, making no difference; not on a family comma's surname, which S3 never read so, not for a title or a given name written short before the stop, nor where the word after the stop is suffix vocabulary, which reports itself (S11).
  ```
  "John Smith B.Eng"          →  ambiguities=("suffix-or-name",)
  "John Smith A.Brown, PhD"   →  ambiguities=("suffix-or-name",)
  "Dr. A.Smith"               →  ambiguities=()
  ```

**Because:** a name glued to the title or initial before it is the same name written without its space, Mongolian writes every short form that way (`У.Хүрэлсүх`), and in the part before a comma the word after a chunk read on its own is a name in nearly every case that the local corpora hold. After a comma the same shape is a degree written with its field (`Dr.med`, `M.Sc`, `B.Chir`), so the division stops at the comma.

**Except:**

- **A word the vocabulary reads whole** keeps its reading: a suffix spelled without its stops, a credential every chunk of which counts, a word whose every chunk is a title, and a title listed with its stops, such as a degree written with its field's initial.
  ```
  "John Smith M.Sc"           →  suffix="M.Sc"
  "Lt.Gov. John Smith"        →  title="Lt.Gov."
  "Dr.C. Andrés Saavedra"     →  title="Dr.C."
  "Mgr.A. Marek Rejent"       →  given="Marek"
  ```
- **A word after a comma** keeps its one word, the slot after a comma being where degrees stand.
  ```
  "Ole Simonsen, Dr.Med"      →  title="Dr.Med"
  "Smith, Dr.John"            →  title="Dr.John"  · boundary
  ```
- **A word the shape refuses** keeps its one word: a name in lower case after the stop, one closed by its own stop or followed by another chunk, an unambiguous title or credential, and a word holding a delimiter or a digit.
  ```
  "Dr.med. Lukas Mayer"       →  title="Dr.med."
  "J.Smith. Jones"            →  given="J.Smith."
  "Dr.MD Smith"               →  title="Dr.MD"
  ```
- **A saint particle glued to a name is one name word**, read neither as a title nor as a credential by its dotted shape, since `St John` is also a given name and a middle name, which written apart it would not stay; only as the last name word of the part, right behind a name (no title of any kind, and no connective earlier in the part, which joins a title phrase), where the family ends the part (before a family comma, or under an order that ends the name with the family), does it divide, so P10's saint run opens the surname as written apart.
  ```
  "St.John Price"             →  given="St.John"
  "Jeremy St.John Middleton"  →  middle="St.John"
  "Mark Jhon Sta.Ana"         →  family="Sta.Ana"
  "Juan dela Cruz Sta.Maria"  →  middle="dela Cruz"
  "Mr. St.Clair"              →  family="St.Clair"
  "Mr and Mrs St.Clair"       →  family="St.Clair"
  ```

**Precedence:**

- **An initial or a title glued to the surname before a comma** ("Mr.Smith, J.P."): the division comes first, and C16 counts the divided head as it counts the spaced one, so the head is the two words of `Mr. Smith`.
  ```
  "Mr.Smith, J.P."            →  suffix="J.P."
  ```
- **A suffix word that is also a name, glued behind an initial** ("Pedro M.Filho"): the division comes first, and S11 weighs the word as it is written apart.

**Accepted:**

- A name glued to its chunk and closed by a stop of its own stays one word ('J.Smith.', 'Mrs.Smith.'), the stop being how a field is closed too ('Dr.Med.').
- In a name written wholly in lower case nothing after the stop has the capital the test reads, so it stays one word ('dr.john smith'), where its capitals divide ('DR.JOHN SMITH'), and a saint particle glued to a name keeps the reading its chunks give it there ('st.john price' title 'st.john').
- A saint word followed by another name word stays one word where its spaced writing reads a saint run opening the surname: `Juan Sta.Maria Reyes` reads middle 'Sta.Maria', family 'Reyes', where `Juan Sta. Maria Reyes` reads family 'Sta. Maria Reyes' (P10), the price of keeping the British middle name whole ('Jeremy St.John Middleton').
- A listed title before the initials is no word to spare, though rarely a given name, so the report is not made there ('Vice A.Smith').
- `Parser.revise` reads a value on its own, so a glued word in it divides, and the revised field renders the pieces apart ('M.Hassan' revising to 'M. Hassan'), as a CJK value's own parse divides it.
- After a family comma a glued word stays whole though it is the given name the comma names ('SMITH, J.MICHAEL' → given 'J.MICHAEL').
- An unlisted credential glued at its stop and ending the name divides as a name would, reported ('John Smith B.Eng' → family 'Eng'); a degree spelled as a title and its field before any comma divides too ('Dr.Med Hans Meier' → given 'Med'), as does a degree spelled as a title and one letter that no entry lists with its stops.
  ```
  "Sabiha Arshad M.Phill"     →  family="Phill"
  ```
- A degree listed with its stops is read whole where its letter is an initial behind the title ('Dr.C Kamaraj' → title 'Dr.C', and so 'Mgr.A Novák'), the Cuban and Czech degrees so spelled being the commoner writing.
  ```
  "Dr.C Kamaraj"              →  title="Dr.C"
  ```

---
**Signal:** shape: a chunk read alone, a full stop and a name, written as one word before any comma; for the report, the word's place at the end of the name behind a word to spare
**history:** decisions/T8 · **implemented:** nameparser/_pipeline/_script_segment.py, nameparser/_pipeline/_vocab.py
