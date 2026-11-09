# N2 — same-character quotes and shared-character conventions

**When:** a quote character stands in a name where it could open or close a clause, either because its open and close are the same character or because two conventions share it, as in "Sean O'Connor".

**Then:** a quote whose open and close are the same character opens only at a word start and closes only at a word end, so an apostrophe inside or at the end of a word is literal.

- **Between conventions that share a character, position in the text decides:** the leftmost valid opener wins.
  ```
  "Hans „Erster“ und “Zweiter” Müller"  →  nickname="Erster Zweiter"
  ```
- **A dangling-open report is suppressed where its character sits inside another pair's successful match**, being literal content there rather than an imbalance (A1 depends on that filter).

**Because:** only a mark standing at word boundaries is quoting; anywhere else it is part of the word.

```
"Sean O'Connor"             →  family="O'Connor"
"Mari' Aube'"               →  family="Aube'"  · boundary
```

**Except:**

- **An apostrophe opening a word the vocabulary lists as a particle** is part of that word, so it opens no quote.
  ```
  "Jan van 't Hof 'Jantje'"  →  nickname="Jantje"
  ```

**Accepted:**

- A quote that does open at such a word is read as the word, its close staying in the word it ends.
  ```
  "Pieter 't Hart' Smith"  →  family="'t Hart' Smith"
  ```

---
**Signal:** position: where a same-character quote stands in its word + neighbor: the word the apostrophe opens, looked up as a particle
**history:** decisions/N2 · **implemented:** nameparser/_pipeline/_extract.py
