# C10 — a suffix delimiter parts a suffix run

**When:** a suffix delimiter, the semicolon or one the policy declares, stands after the first comma, alone in a trailing suffix part, as in "Smith, John, PhD - and MD", or glued to a word, as in "John Smith, MD; PhD".

**Then:** a suffix delimiter parts the suffix words on each side of it as a comma would: the words on each side of it read exactly as the parts of the same text written with a comma in its place, so no join, maiden clause or connective reaches across it.

- **The semicolon is a delimiter by default**, beside the comma: a delimiter the policy declares is one more, and no policy removes the semicolon, as none removes the comma.
- **A delimiter standing alone is dropped**, unless it stands alone as the whole of its part.
- **A delimiter glued to a suffix word parts it from the next as a comma glued there would**: the word keeps the delimiter in its text and reads as it would without it, so the part after the first comma reads as it does with a space in the delimiter's place, its word joining no word after the delimiter. Only a delimiter written without a letter or digit is glued: one that is itself a word parts only standing alone, a word holding its letters being another word ("Stand" under " and ").
- **Only a trailing part is parted by a delimiter standing alone**: in the part before the first comma, or in the given part of the listing form (C8), such a delimiter is a word (the second Accepted bullet).

**Because:** a writer who separates suffixes with a semicolon, or a caller who declares a separator, means it to separate suffixes as a comma does, and the simplest reading that honours that is one where it is a comma there.

```
"John Smith, MD; PhD"                 →  suffix="MD; PhD"
"John Smith, MD;PhD"                  →  suffix="MD;PhD"
"John Smith, M.D.; Ph.D."             →  family="Smith"
"Smith, MD; PhD"                      →  suffix="MD; PhD"
"John Smith, MA; PhD"                 →  suffix="MA; PhD"
"John Smith, Dr; MD"                  →  title="Dr;"
"Smith, John, PhD - and MD" extra_suffix_delimiters-dash →  suffix="PhD, and MD"
"Smith, John, Puig - i Soler" extra_suffix_delimiters-dash →  suffix="Puig, i Soler"
"Smith, John; MD"                     →  given="John;"  · boundary
"Smith, RN - CRNA" extra_suffix_delimiters-dash →  suffix="RN - CRNA"  · boundary
```

**Except:**

- **A glued word written like an initial** is the given name wherever its space twin's is, behind one name word as C1 reads it and under the strict comma-suffix switch (C14).
  ```
  "Smith, V; MD"                      →  given="V;"
  "John Smith, V; MD" strict-comma-suffixes →  given="V;"
  ```

**Precedence:**

- **A glued part behind a head that is not a whole name** ("Smith, MD; PhD"): the part reads as its space twin does, the credential opening it making it the postnominal part (C13), so C10 decides nothing there that C1 does not.

**Accepted:**

- A maiden marker in a part a declared delimiter separates takes no clause. The delimiter costs nothing here: a marker in a part after a suffix comma is an ordinary word with or without a core (M2), so 'Smith, John, MD née Jones Smith' takes none either. Releases 2.0 through 2.3 read past the delimiter and took the clause.
  ```
  "Smith, John, MD - née Jones Smith" extra_suffix_delimiters-dash →  suffix="MD, née Jones Smith"
  ```
- A delimiter core the policy names (T1) is a word here, not structure — v1 applied the delimiter to the suffix-comma form alone, and that limitation is kept as parity: the core in 'Smith, RN - CRNA' is a word under the policy as without it. Since #603 it is a word of the run the credential opens, so the part reads suffix "RN - CRNA" where 2.0 through 2.3, like v1, read given "RN".
  ```
  "Smith, RN - CRNA"          →  suffix="RN - CRNA"
  ```
- A delimiter standing alone behind a whole name renders as a comma, being dropped, while a glued one stays in the word it is glued to: the suffix view writes 'MD, PhD' for "John Smith, MD ; PhD" and 'MD; PhD' for "John Smith, MD; PhD". Behind one name word, or none, a semicolon standing alone is a word of the run the credential opens, as a declared core is there, one rule for every delimiter.
  ```
  "John Smith, MD ; PhD"      →  suffix="MD, PhD"
  "Smith, MD ; PhD"           →  suffix="MD ; PhD"
  ```
- A glued word read by its letters rather than its vocabulary is not read as the word without it: a credential written as two period-marked pieces with the delimiter glued to the second, and a one-letter numeral ending the given part, keep the readings 2.0 through 2.5 gave them where their space twins read a suffix.
  ```
  "John Smith, Ph. D.; MD"    →  given="D.;"
  "Smith, John V;"            →  middle="V;"
  ```

---
**Signal:** separator: the semicolon or a delimiter the caller declared, after the first comma
**history:** decisions/C10 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_comma.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_segment.py, nameparser/_pipeline/_vocab.py
