# S6 — the case signal at the suffix slot

**When:** a member of the ambiguous class (S4) stands where a suffix may stand, as in "Jack MA".

**Then:** written case is evidence beside the count (S4), and it speaks only in a name written in more than one case: there a member of the ambiguous set written in capitals reads as the credential even with no words to spare, and one written in any other cased form that is not wholly lower reads as the name even with words to spare.

- **A name written wholly in one case says nothing about any word in it**, and the count decides alone; so does a script with no case to write in.
  ```
  "JACK MA"                   →  family="MA"  · boundary
  ```
- **At the trailing slot of the given part** after a family comma, the comma has already settled the count, so the writing is the only evidence there is (S5).
- **A generation word that is also a name (S11) is written the other way at one end**: its lower case in a name of mixed case is the generation even with no word to spare, its capitals say nothing, a surname being often written in them, and its Title case leans to the name as an acronym's does. An agnomen's writing says nothing at all, since it takes the case of the name around it.
  ```
  "Dumas fils"                →  suffix="fils"
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

**Precedence:**

- **The first slot after a comma** ("Smith, Ma", "John Smith, Ma"): this evidence is SECOND there: the count of name words before the comma decides there first (C4), and the case is read only where that count leaves the word a name.
  ```
  "Smith, MA"                 →  suffix="MA"
  "Smith, Ma"                 →  given="Ma"
  ```
- **A part of listed members written in capitals, at the first slot after a comma** ("Smith, MA MA"): C4 states the one exception: a part of two or more suffix words and words of this class, every word of the class listed and written in capitals in a mixed-case name, is read on its capitals before the count is asked, as the credential run behind one name word as behind two ('Smith, MA MA' reads suffix 'MA MA'), and only a word of the class opening the part reports, as the first word after the comma ('John Smith, MA MA' reports on the first 'MA' alone, where a counted flip reports over the whole part; the reports are C11's).

---
**Signal:** case contrast: capitals on a word of the ambiguous class in a name written in more than one case
**history:** decisions/S6 · **implemented:** nameparser/_pipeline/_vocab.py, nameparser/_render.py
