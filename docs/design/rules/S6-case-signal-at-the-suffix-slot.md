# S6 — the case signal at the suffix slot

**When:** a member of the ambiguous class (S4) stands where a suffix may stand, as in "Jack MA".

**Then:** written case is evidence beside the count (S4), and it speaks only in a name written in more than one case: there a member of the ambiguous set written in capitals reads as the credential even with no words to spare, and one written in any other cased form that is not wholly lower reads as the name even with words to spare.

- **A clash settled by the writing is not reported**: a listed member its capitals read as the credential is no longer a word that might be either, as one written with its periods is not (S3), so no `suffix-or-name` report names it at any slot S4, S5 or C4 reads it. Only the clash with the name reading is settled: the word keeps its other readings, so a particle reading (`DO`) answers P6 as before, and a member's capitals start the credential's trailing run as a credential's do, where S8 says they do (S8).
  ```
  "John Smith MA"             →  ambiguities=()
  "Jack MA"                   →  ambiguities=("given-or-family",)
  "John Smith, MA"            →  ambiguities=()
  "Doe, John DO"              →  family="Doe"
  "Doe, John DO"              →  ambiguities=()
  "John Smith Ma"             →  ambiguities=("suffix-or-name",)
  ```
- **A name written wholly in one case says nothing about any word in it**, and the count decides alone and reports as S4 says; so does a script with no case to write in. The case asked of a word in a maiden clause or between brackets is the whole name's, the clause and the brackets being no name of their own.
  ```
  "JACK MA"                   →  family="MA"  · boundary
  "JOHN SMITH MA"             →  ambiguities=("suffix-or-name",)
  ```
- **At the trailing slot of the given part** after a family comma, the comma has already settled the count, so the writing is the only evidence there is (S5).
- **A generation word that is also a name (S11) is written the other way at one end**: its lower case in a name of mixed case is the generation wherever the name keeps a family word, never with none to spare (S11), its capitals say nothing, a surname being often written in them, and its Title case leans to the name as an acronym's does. An agnomen's writing says nothing at all, since it takes the case of the name around it.
  ```
  "Dumas, Alexandre fils"     →  suffix="fils"
  "Dumas fils"                →  family="fils"  · boundary
  "Marie FILS"                →  family="FILS"
  "Jean Marie Fils"           →  family="Fils"
  "Dumas, Alexandre Fils"     →  middle="Fils"
  "Pedro Alves Neto"          →  suffix="Neto"
  ```

**Because:** in a name written in more than one case, the writer's capitals are evidence the count does not have: credentials are written in capitals and names are not. A name written in one case carries no such evidence.

```
"Jack MA"                   →  suffix="MA"
"Jack Ma"                   →  family="Ma"
"John Smith Ma"             →  family="Ma"
"john smith MEng"           →  family="MEng"
```

**Except:**

- **Where something before the writing keeps the word a name, it reports as before**: with nothing in front of a comma C4's count leaves the word after it the given name, the case being read only behind one name word (C4), and the first word after a maiden marker is the maiden name the marker announced (M2), whatever case either is written in.
  ```
  ", MA Smith"                →  given="MA"  · boundary
  ", MA Smith"                →  ambiguities=("suffix-or-name",)  · boundary
  "Jane Doe nee MA"           →  ambiguities=("suffix-or-name",)  · boundary
  ```

**Precedence:**

- **The first slot after a comma** ("Smith, Ma", "John Smith, Ma"): this evidence is SECOND there: the count of name words before the comma decides there first (C4), and the case is read only where that count leaves the word a name.
  ```
  "Smith, MA"                 →  suffix="MA"
  "Smith, Ma"                 →  given="Ma"
  ```
- **A part of listed members written in capitals, at the first slot after a comma** ("Smith, MA MA"): C4 states the one exception: a part of two or more suffix words and words of this class, every word of the class listed and written in capitals in a mixed-case name, is read on its capitals before the count is asked, as the credential run behind one name word as behind two ('Smith, MA MA' reads suffix 'MA MA'), and the writing having settled every word of the class in it, the part reports nothing (C11).

---
**Signal:** case contrast: capitals on a word of the ambiguous class in a name written in more than one case
**history:** decisions/S6 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_comma.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py, nameparser/_render.py
