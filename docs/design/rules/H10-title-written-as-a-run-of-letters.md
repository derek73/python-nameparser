# H10 — a title written as a run of letters

**When:** a run of single letters joined by full stops whose spelling without them is a title the vocabulary marks as written that way stands in a title run at the head of a name, as in "U.S. District Judge Marc Treadwell".

**Then:** the run reads as that title where a title the run keeps stands behind it, after H3's floor has given its word back, and otherwise it is the initials it is written as.

- **A run with no title behind it is given back to the name**, whether nothing follows it but name words, a title opens the run in front of it, or H3's floor has returned the title behind it; and before a family comma, where H6 reads the run, it is given back to the family.
  ```
  "U.S. Grant"                →  given="U.S."
  "Hon. U.S. Grant"           →  title="Hon."
  "Hon. U.S. Grant"           →  given="U.S."
  "U.S. Senator Jr"           →  family="Senator"
  "U.S. Grant Smith, John"    →  family="U.S. Grant Smith"
  ```

**Because:** an abbreviation of several words is written with a stop after each letter, and two initials are written the same way and spell many short titles (D.R., M.R., M.S.). A title behind the run tells the two apart, since initials stand before a name, not before a title. Only the titles that abbreviate several words are marked, because a title that abbreviates one word (Dr, Mr, Lt) is never written with a stop between its letters, so that writing of it is always initials.

```
"U.S. District Judge Marc Thomas Treadwell"  →  title="U.S. District Judge"
"U.S. Senator John Smith"   →  given="John"
"Hon. U.K. Ambassador Jane Smith"  →  title="Hon. U.K. Ambassador"
"P.D. Dr. Hans Meier"       →  title="P.D. Dr."
"U.S. Marshal John Smith"   →  title="U.S. Marshal"
"U.S. Senator Smith, Ed"    →  given="Ed"
"Treadwell, U.S. District Judge Marc"  →  title="U.S. District Judge"
"U.S. Senator Smith, John"  →  title="U.S. Senator"
"US Senator John Smith"     →  title="US Senator"  · boundary
```

**Except:**

- **Initials that spell a title the vocabulary does not mark stay a name**, a title word behind them or not.
  ```
  "D.R. Judge Smith"          →  given="D.R."
  "M.S. Pope Jones"           →  given="M.S."
  ```

**Precedence:**

- **Paired initials opening the part after a comma** (C5): C5 keeps them as the given part rather than the credential, and where a title the run keeps follows them, they are this rule's title.
  ```
  "García Márquez, U.S. Senator John"  →  title="U.S. Senator"
  "García Márquez, U.S. Grant"  →  given="U.S."
  ```

**Accepted:**

- A person whose initials spell a marked title and whose next name is a title word reads the initials as the title. P.D. is common as initials in India, and no name in the corpora decisions/H10 lists was read this way when the rule was measured.
  ```
  "P.D. Judge Smith"          →  title="P.D. Judge"
  ```
- Where the comma's decision has reported the run, the part's opening paired initials (C11), the report stands though this rule reads the run as a title, the credential being its other reading.
  ```
  "Smith, U.S. Senator John"  →  ambiguities=("suffix-or-name",)
  ```
- A run a connective joins to another reads as a name with it, being one unit of several words rather than a run of letters.
  ```
  "U.S. and U.K. Ambassador Jane Doe"  →  given="U.S. and U.K."
  ```
- Wherever the run stands, a title that is also a given name reads it as the title it spells when asking for a partner in its title phrase (H9), as it reads the run's spelling without stops, so a gated title ending the name behind it is the trailing title and the run a name word.
  ```
  "John Smith U.S. Dean."     →  title="Dean."
  "John Smith U.S. Dean."     →  family="U.S."
  ```
- The run reads as a title only at the head of a name. At the end of one, H5's trailing run does not take it, as it does not take the run's spelling without stops either.
  ```
  "John Smith U.S. Senator"   →  family="Senator"
  ```

---
**Signal:** neighbor: a title the run keeps behind a run of single letters whose spelling without its stops is title vocabulary marked as written that way
**history:** decisions/H10 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_vocab.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_assign.py
