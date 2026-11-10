# T7 — a given name written as a run of initials

**When:** the given name is a run of single letters joined by full stops, written in capitals with a family name beside it, as in "E.T. Smith".

**Then:** it reads as its letters written with a space between them would: the letter in the given name's place in the order is the given name, and the others are middle names.

- **The order places the given name.** Given first or family first, the first letter is the given name; where the order lays the given name out after the middle names, the last letter is.
  ```
  "E.T. Smith"                →  given="E."
  "E.T. Smith"                →  middle="T."
  "J.R.R. Tolkien"            →  middle="R.R."
  "Smith E.T."  family-first  →  given="E."
  "Smith E.T."  family-first-given-last  →  given="T."
  ```
- **A family comma names a family**, so the run after one parts though the comma names none (C15), and a report the comma made on the run names its letters.
  ```
  "Smith, E.T."               →  given="E."
  ", E.T."                    →  given="E."
  "Smith, E.T."               →  ambiguities=("suffix-or-name",)
  ```
- **The writing stays as it was written**: the letters join with nothing between them (R1), and a run of single letters joined by full stops, in capitals, gives one initial per letter wherever the parse left it whole.
  ```
  "E.T. Smith"                →  str="E.T. Smith"
  "E.T. Smith"                →  initials="E. T. S."
  "John E.T. Smith"           →  initials="J. E. T. S."
  ```

**Because:** initials are written run together as often as apart, and the writer means the same name by both. A run in the given name's place is the given name and the middle names after it, which is how the same letters written apart are read.

**Except:**

- **A run in lower case** keeps its one word, in a name of mixed case and in one written wholly in lower case: it may be an abbreviation of its own, as honoris causa is, and a name in one case says nothing either way.
  ```
  "Dr. h.c. Hans Meier"       →  given="h.c."
  "Dr. h.c. Hans Meier"       →  initials="h. H. M."
  "e.t. smith"                →  given="e.t."
  ```
- **A run in another field** keeps its one word: a middle name's run, and the family name some surnames are written as (B.K.).
  ```
  "John E.T. Smith"           →  middle="E.T."
  "Ram Bahadur B.K."          →  family="B.K."
  ```
- **A run with no family name beside it** and no family comma keeps its one word, the run being all the name holds.
  ```
  "E.T."                      →  given="E.T."  · boundary
  ```
- **A policy that moves a middle name** keeps the run whole: `middle_as_family` would fold a letter into the family, and `two_given_names` would read a second letter as a given name.
  ```
  "E.T. Smith"  middle_as_family  →  given="E.T."
  "E.T. Smith"  two_given_names  →  given="E.T."
  ```

**Accepted:**

- A credential written as a run where the parse reads a name word parts with it, as the same letters written apart would: under the Vietnamese pack's given-last order `Nguyen Van Anh D.O.` reads middle 'Van Anh D.', given 'O.'.

---
**Signal:** shape: a run of single letters joined by full stops in the given name
**history:** decisions/T7 · **implemented:** nameparser/_pipeline/_assemble.py, nameparser/_pipeline/_vocab.py, nameparser/_render.py
