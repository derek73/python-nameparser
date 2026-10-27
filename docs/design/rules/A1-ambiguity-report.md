# A1 — the ambiguity report

**When:** the text's structure or a word's reading is genuinely uncertain, as in "Van Johnson".

**Then:** the parse completes on the best reading and carries an ambiguity report naming the doubt, as parsing never fails on any input.

- **A report names the reading the parse took**, so a report whose fork the rest of the parse then resolved to NEITHER branch is withdrawn rather than carried beside a reading it contradicts: a letter both a connective and an initial (P8), read as the generation it also spells, is neither of the two the connective-or-initial fork offered, and only that fork's report goes — the generation's own stands.
  ```
  "JOHN QUINCY SMITH I"       →  ambiguities=("suffix-or-name",)
  ```
- **A report that names the field its word was read into names the field the word holds in the result**, whatever rule moved it after the report was made.
- **A report of a fork carries the reading the parse did not take**: its kind, its source, and the field the word would land in with every other word read as the parse read it, save a reading no field could hold, a connective with no word before it to join.

**Because:** a caller can only act on doubt that is reported.

```
"Van Johnson"               →  ambiguities=("particle-or-given",)
"Jane „JD Smith"            →  ambiguities=("unbalanced-delimiter",)
"John Smith, MD, Bart"      →  ambiguities=("comma-structure",)
"John Smith"                →  ambiguities=()  · boundary
```

**Accepted:**

- The one exception to totality is a user-supplied segmenter's own error, which propagates — a user-code error is not a content error. (Needs the optional extra to demonstrate, so no example line.)

---
**Signal:** none of its own: the forks the other rules call, and whether the parse kept a reading either offered
**history:** decisions/A1 · **implemented:** nameparser/_pipeline/_assemble.py, nameparser/_pipeline/_state.py
