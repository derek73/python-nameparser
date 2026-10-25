# C1 — the suffix-comma decision

**When:** a name holds a comma, as in "Smith, John" or "John Smith, PhD".

**Then:** the name reads as trailing suffixes when the part after the first comma is entirely suffix words and more than one word precedes the comma, and otherwise as the listing form, the part before the comma being the family name, less a title run opening it (H6), unless the part after it fixes no family boundary (C8).

- **Only the part after the first comma decides**, but for a suffix word ending a whole name before it (C12).
- **How the words before the comma are counted** is C3's.
- **The ambiguous credential class**, counted by name words (C4), with paired initials (C5) and an unlisted all-caps word (C6) read there by rules of their own.
- **A part read as postnominal** is read before any join (C7).
- **The listing form's part after the comma** is still read for what it is (C8), and a credential opening it makes it the postnominal part (C13).
- **A one-character suffix word inside a comma part** is read by what stands before it (C9).
- **A suffix delimiter**, the semicolon or one the policy declares, parts the suffix words on each side of it as a comma would (C10).
- **What the decision reports** is C11's.

**Because:** a credential run after the comma means the name is in natural order with suffixes appended; anything else after the comma means the listing form.

```
"Smith, John"               →  family="Smith"
"سلمان، محمد"               →  family="سلمان"
"田中、太郎"                 →  family=""
"John Smith, PhD"           →  suffix="PhD"
"John Smith, V."            →  suffix="V."
"Smith, PhD"                →  family="Smith"  · boundary
"John Smith, Jones"         →  family="John Smith"
```

**Precedence:**

- **A suffix word written like an initial** ("John Smith, V."): by default a recognized suffix word counts even written like an initial ("V."); under the strict comma-suffix switch C14 governs, and the word is vetoed.
- **The count against written case** ("Smith, MA", "Smith Jr., Ma"): C4 counts the name words before the comma first and asks written case (S6) second, only where the count has left the word a name.
- **Paired initials against the count** ("García Márquez, G.J."): C5 is the stated exception to C4's count, since two words before the comma may be one surname written in two.
- **An unlisted all-caps word** ("John Smith, XYZ"): C6 decides whether it joins C4's class at all, only where the name carries a case contrast, and once it has joined, C4's count reads it.
- **A generation ending the name before the comma against paired initials after it** ("John Smith Jr., M.J."): written dotted, the initials keep C5's reading and are the given name, the generation staying the suffix; written undotted as two capitals, they are C12's credential, read as the credential they look like. A numeral ending the family part is read as the comma-less name reads it (S10), so the roman numerals S10 reads by their shape stay the suffix as the listed ones do.
  ```
  "John Smith Jr., M.J."      →  given="M.J."
  "John Smith Jr., MJ"        →  suffix="Jr., MJ"
  "John Smith V, M.J."        →  suffix="V"
  "John Smith VI, M.J."       →  suffix="VI"
  ```

**Accepted:**

- The vocabulary question this rule asks — is the part after the comma nothing but suffix words — is asked a second time, without the word-count condition, to decide whether a glued East Asian honorific standing before a family comma comes off. That composition is tolerated input rather than contract — a comma between a family name and a given name is no part of CJK writing — so the precedence is stated at W3, with its examples, and not here. It is also the one consequence of this question Latin script cannot witness, nothing there being glued to the end of a name — which is why this bullet carries no example of its own.

---
**Signal:** hub of C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13
**history:** decisions/C1 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_comma.py
