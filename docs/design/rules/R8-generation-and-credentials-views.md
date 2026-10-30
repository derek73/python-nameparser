# R8 — the generation and credentials views

**When:** the suffix of a parsed name is read by what each of its words is, as in "Smith, John, Jr., MD, Esq.".

**Then:** the suffix splits into two views that partition it, the generation holding its words read as a generation or an agnomen and the credentials holding every other word, each joining its words in written order and separating two of them as the writer did (R1), by a comma where one stands anywhere between them and by a space where none does.

**Because:** a generation numbers the bearer among relatives of the same name while a credential is earned, and CLDR's person-name fields keep the two apart and format them differently. A caller wanting one had to re-read the suffix against vocabulary they would have had to rebuild (#326). Both are views, so the suffix field itself does not change.

```
"Smith, John, Jr., MD, Esq."  →  generation="Jr."
"Smith, John, Jr., MD, Esq."  →  credentials="MD, Esq."
"Smith, John, Jr., MD, Esq."  →  suffix="Jr., MD, Esq."
"Dr. Juan Q. Xavier de la Vega III"  →  generation="III"
"Pedro Alves Filho"         →  generation="Filho"
"John Smith Esq."           →  credentials="Esq."
"王小明先生"                  →  credentials="先生"
"John Smith Jr. III PhD"    →  generation="Jr. III"
"John Smith Jr. III PhD"    →  credentials="PhD"
"John Smith Ph. D. Jr."     →  credentials="Ph. D."
"John Smith, MD Jr. PhD"    →  credentials="MD PhD"
"John Smith, MD, Jr. PhD"   →  credentials="MD, PhD"
"John Smith PhD"            →  generation=""
"John Smith"                →  generation=""  · boundary
"John Smith"                →  credentials=""
```

**Except:**

- **A connective in the suffix** is in the view of the word before it, being read as neither a generation nor a credential.
  ```
  "John Smith, Jr. and III"   →  generation="Jr. and III"
  "John Smith, PhD and MD Jr."  →  credentials="PhD and MD"
  ```

**Accepted:**

- A word of the suffix vocabulary that is neither a generation nor a credential (a courtesy, an honorific, a status) is in the credentials, CLDR's catch-all, since CLDR has no third field; its reading's kind, a post-nominal word, tells it apart for a caller who needs it.
- A connective joining a generation to a credential is left at the end of the generation, the view of the word before it.
  ```
  "John Smith, Jr. and MD"    →  generation="Jr. and"
  ```
- A suffix word with no reading, one that `replace()` or `Parser.revise()` wrote, is in the credentials whatever it is, since nothing records what it was read as.
- The kind of a word listed as a suffix word is the shipped vocabulary's, read whatever the reading's default, so a word only a caller's own `Lexicon` lists is in the credentials, a generation word included, and so is a generation word a caller lists as an acronym.

---
**Signal:** none in the name: the reading each suffix word took, and the separators the writer typed between them
**history:** decisions/R8 · **implemented:** nameparser/_types.py, nameparser/_pipeline/_vocab.py
