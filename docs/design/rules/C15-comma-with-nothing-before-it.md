# C15 — a comma with nothing before it

**When:** a name opens with a comma that has nothing written before it, as in ", John Smith".

**Then:** the comma is a family comma (C1) naming no surname, and the part after it reads as the given part after a family comma reads, with no surname supplied for it.

**Because:** a comma with nothing before it is how a listing writes a record whose surname field is empty, as CSV data writes one. The writer marked where the surname goes and left it empty, so the parser supplies none, and a floor that keeps a family word does not apply, the input naming no family to lose. Read this way the shape has no reading of its own: the part reads as it reads behind any surname.

```
", John Smith"              →  given="John"
", John Smith"              →  middle="Smith"
", John Smith"              →  family=""
", John Smith Jr."          →  suffix="Jr."
", John (Bob) Smith"        →  nickname="Bob"
", PhD"                     →  suffix="PhD"
", Jr."                     →  suffix="Jr."
", Sir John"                →  given="John"
```

**Except:**

- **A title and one name word** (H1): the comma names no surname, so it does not decide the field of that word, or of a bound pair standing for it, and the title's lone name word reads as the family. A particle that is also a suffix word, ending the name behind a title that addresses by surname, then has no family to attach to (P6) and reads as the suffix.
  ```
  ", Dr. John"                →  family="John"  · boundary
  ", Jane Mrs"                →  family="Jane"
  ", Dr. abdul Rahman"        →  family="abdul Rahman"
  ", Dr. Jones vd"            →  suffix="vd"
  ```

**Precedence:**

- **A particle ending the name** (P6) attaches to the family after this comma as after any family comma, and with no surname written the family is that particle alone: `, Jane van` reads family `van`. P6 wins because the particle is in the part after the comma, which this rule reads as any given part is read.
  ```
  ", Jane van"                →  family="van"
  ", Sir Jones vd"            →  family="vd"
  ```

**Accepted:**

- A writer with a stray comma in front of a whole name gets the listing reading rather than the name's: `, John Smith` reads given `John`, middle `Smith`, where `John Smith` reads family `Smith`. The shape's one source is an empty surname field, and dropping the comma would contradict it.
  ```
  ", John Smith"              →  family=""
  "John Smith"                →  family="Smith"
  ```
- The surname's case is evidence the empty head does not have. A word of the ambiguous credential class written alone in capitals reads as a name, the name being written wholly in one case (S6), where a surname written in mixed case before the comma makes the same word the credential.
  ```
  ", MA"                      →  given="MA"
  "SMITH, MA"                 →  given="MA"
  "Smith, MA"                 →  suffix="MA"
  ```

---
**Signal:** comma: nothing written before the first comma
**history:** decisions/C15 · **implemented:** nameparser/_pipeline/_comma.py
