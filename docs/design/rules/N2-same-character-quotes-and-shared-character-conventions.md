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

- **An apostrophe opening a word the vocabulary lists as a particle**, alone or hyphened to the name after it, is part of that word, so it opens no quote, unless the next apostrophe of the same character in the name stands after a character other than whitespace.
  ```
  "Jan van 't Hof 'Jantje'"   →  nickname="Jantje"
  "Arent van 's-Gravesande"   →  family="van 's-Gravesande"
  "Arent van 's-Gravesande"   →  ambiguities=()
  "Bob 'T Bone' Smith"        →  nickname="T Bone"  · boundary
  "Bob 'T-Bone Jones' Smith"  →  nickname="T-Bone Jones"  · boundary
  ```

**Accepted:**

- A quote with no apostrophe after it opening at a listed particle is read as the word, with no report.
  ```
  "Aaron 'T-Bone Walker"  →  middle="'T-Bone"
  "Aaron 'T-Bone Walker"  →  ambiguities=()
  ```
- An apostrophe inside a later word stands after a letter, so a listed particle before it opens a quote as it did through 3.0.1, though that apostrophe cannot close one, and the quote reports.
  ```
  "Gerard 't Hooft d'Hondt"  →  family="'t Hooft d'Hondt"
  "Gerard 't Hooft d'Hondt"  →  ambiguities=("unbalanced-delimiter",)
  ```

---
**Signal:** position: where a same-character quote stands in its word + neighbor: the word the apostrophe opens, looked up as a particle
**history:** decisions/N2 · **implemented:** nameparser/_pipeline/_extract.py
