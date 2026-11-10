# T7 — a given name written as a run of initials

**When:** the given name is a run of single letters joined by full stops, written in capitals or in a name written wholly in lower case, with a family name beside it, as in "E.T. Smith".

**Then:** it reads as its letters written with a space between them would: the letter in the given name's place in the order is the given name, and the others are middle names.

- **The order places the given name.** Given first or family first, the first letter is the given name; where the order lays the given name out after the middle names, the last letter is.
  ```
  "E.T. Smith"                →  given="E."
  "E.T. Smith"                →  middle="T."
  "J.R.R. Tolkien"            →  middle="R.R."
  "Smith E.T."  family-first  →  given="E."
  "Smith E.T."  family-first-given-last  →  given="T."
  "e.t. smith"                →  given="e."
  "Dr. j.r. smith"            →  given="j."
  ```
- **A family comma names a family**, so the run after one parts though the comma names none (C15), and a report the comma made on the run names its letters.
  ```
  "Smith, E.T."               →  given="E."
  ", E.T."                    →  given="E."
  "Smith, E.T."               →  ambiguities=("suffix-or-name",)
  ```
- **The default rendering keeps the run as it was written**: the letters join with nothing between them where they stand side by side (R1), and the initials give one letter each (R3).
  ```
  "E.T. Smith"                →  str="E.T. Smith"
  "E.T. Smith"                →  initials="E. T. S."
  ```

**Because:** initials are written run together as often as apart, and the writer means the same name by both. A run in the given name's place is the given name and the middle names after it, which is how the same letters written apart are read.

**Except:**

- **A run in lower case among capitals** keeps its one word: the capitals of the given, middle and family names around it say it is no run of initials, and it may be an abbreviation of its own, as honoris causa is. Names written wholly in lower case say nothing about any letter, and read as their capitals do, a title in capitals beside them included.
  ```
  "Dr. h.c. Hans Meier"       →  given="h.c."
  "Dr. h.c. Hans Meier"       →  initials="h. H. M."
  ```
- **A run the vocabulary lists as a word of its own** keeps its one word: a vocabulary entry written with its full stops, or a case mask keyed with them that writes a lower-case letter, or one that writes them, such as a caller's `h.c` for honoris causa; a mask writing the letters as capitals says they are initials. The spelling without stops is not asked, since that is how initials spell a word: J.R. is no Jr, and K.T. no Kt, though the credential's mask writes it in mixed case.
  ```
  "J.R. Smith"                →  given="J."
  "K.T. Smith"                →  given="K."
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

- A spec that renders the given name apart from the middle names renders the parted letters apart: `{given} {family}` gives `E. Smith` for `E.T. Smith`, where it gave the whole run, as it gives `E. Smith` for `E. T. Smith`.
- With a nickname, the rendering lays the name out as it lays out the same letters written apart, the nickname behind the given name, so the run no longer stays together there: `E.T. (Bob) Smith` renders with the nickname between E. and T.
- A lower-case run among capitals and the same run in a name written wholly in lower case read differently, so the two writings of `Dr. h.c. Hans Meier` do not compare equal.
- The order decides where a surname written as initials lands, and in the given name's place it parts: under the family-first, given-last order `Ram Bahadur B.K.` reads given 'K.', middle 'Bahadur B.'.
  ```
  "Ram Bahadur B.K."  family-first-given-last  →  given="K."
  ```
- A run another rule has joined into a longer given name, or counted as one word, keeps the reading that rule gave it, where its letters written apart read differently: a bound given name joins the run (P5, `Abdul E.T. Smith` → given 'Abdul E.T.'), a connective joins it to the next given name (P3, `E.T. and Mary Smith`), and P3's word count reads it as one word (`E.T. Smith y Jones` keeps family 'Smith y Jones').
  ```
  "Abdul E.T. Smith"          →  given="Abdul E.T."
  ```
- A credential written as a run where the parse reads a name word parts with it, as the same letters written apart would: under the Vietnamese pack's given-last order `Nguyen Van Anh D.O.` reads middle 'Van Anh D.', given 'O.'.

---
**Signal:** shape: a run of single letters joined by full stops in the given name
**history:** decisions/T7 · **implemented:** nameparser/_pipeline/_assemble.py, nameparser/_pipeline/_vocab.py
