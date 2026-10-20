# C14 — strict mode: a suffix word written as an initial

**When:** a caller turns the strict comma-suffix switch on, and a suffix word in the part after the comma that the comma's decision (C1) reads is written as an initial, as in "John Smith, V.".

**Then:** strict mode vetoes a word read as an initial, so the word is no suffix word to the comma's decision and a part holding it reads as the listing form's given part (C1).

- **In a name written in one case a bare lower-case letter is vetoed as well**, as its capital is (T4).
  ```
  "john smith, v"  strict-comma-suffixes  →  family="john smith"
  ```
- **A suffix run in the part after the comma ends at such a word** (C9), so the part is no credential run; longer suffix words are not in question.
- **The given part's walk after a family comma does not consult the switch**: a one-character suffix word ending the given part reads there as C9 reads it under the default.

**Because:** one letter, with a period or without, is how an initial is written, and it is also how a one-letter roman numeral is written. By default a recognized suffix word counts at the comma whatever its shape (C1). A caller whose data writes initials after the comma turns the switch on, and the shape decides.

```
"John Smith, V."  strict-comma-suffixes  →  family="John Smith"
"Smith, John V"  strict-comma-suffixes  →  suffix="V"  · boundary
```

**Except:**

- **A credential opening the part** (C13): the veto refuses the word the suffix reading, not the run, so the run the credential opens takes it in as it takes every word after it.
  ```
  "Smith, PSM I."  strict-comma-suffixes  →  suffix="PSM I."  · boundary
  ```

---
**Signal:** none in the name: the strict comma-suffix switch
**history:** decisions/C14 · **implemented:** nameparser/_pipeline/_pieces.py
