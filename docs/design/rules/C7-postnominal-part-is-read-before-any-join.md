# C7 — a postnominal part is read before any join

**When:** the comma's decision (C1) reads a part as postnominal — the credential run, titles beside suffixes, or titles alone — as in "John Smith, Mr. and Mrs.".

**Then:** such a part is read before any join, as its words stand, and that reading is final.

- **The one join made inside it is a connective binding title words into one title** (P3: 'Mr. and Mrs.', a connective run included: 'Minister of the Interior').
  ```
  "John Smith, Mr. and Mrs."  →  given="John"
  "John Smith, Mr. and Mrs."  →  title="Mr. and Mrs."
  "Smith, Chancellor of the Exchequer MP"  →  suffix="MP"
  ```
- **No particle run, connective join or bound given name reaches into it.**
- **The listing form's given part keeps every join** (P2, P3, P5, P6).

**Because:** the comma's decision reads the part after it once, and a join made afterwards could only read the same words differently from the decision.

---
no-boundary: the listing form's given part, which keeps every join, is what P5's own example parses ('Salam, abd Allah').
**Signal:** a sequence, not a signal of its own: a part C1 reads as postnominal is read before any join
**history:** decisions/C7 · **implemented:** nameparser/_pipeline/_comma.py
