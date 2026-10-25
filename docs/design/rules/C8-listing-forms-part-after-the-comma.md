# C8 — the listing form's part after the comma

**When:** the comma's decision (C1) reads the listing form, as in "Smith, PhD".

**Then:** in the listing form the part after the comma is still read for what it is, and a name word in it makes it the given name, with titles before it and suffixes after.

- **A part that is nothing but suffix words is the credential run and reads as suffixes, whole** — the slot after a family comma is postnominal position, so the vocabulary's verdict comes before any title reading of the same word.
  ```
  "Smith, PhD"                →  suffix="PhD"
  "Smith, Jr."                →  suffix="Jr."
  "Smith, Sr."                →  suffix="Sr."
  "Smith, Ph. D. Jr."         →  suffix="Ph. D. Jr."
  "Smith, MD PhD"             →  suffix="MD PhD"
  ```
- **A part that holds no name word at all, titles and suffixes only, fixes no family boundary**, so a part before the comma with more than one name word keeps its positional read, order and all.
  ```
  "Smith, Dr."                →  title="Dr."
  "Smith, Dr. Jr."            →  suffix="Jr."
  "John Smith, Mr."           →  given="John"
  "John Smith, Mr."           →  family="Smith"
  "John Smith, Mr. Jr."       →  given="John"
  "Smith Jr., Mr."            →  family="Smith"  · boundary
  ```

**Because:** a comma fixes a family boundary only where a name word stands after it to be the given name; a part of titles and suffixes alone names nobody.

**Precedence:**

- **A credential opening the part after the comma** ("Doe, PhD Jones"): C13 governs, and the part is postnominal however it goes on, not the given name.

**Accepted:**

- A word of both the title and the unambiguous suffix vocabulary reads as the postnominal after a family comma in every spelling, the honorific's too — position decides for the duals, and the slot is postnominal.
  ```
  "Smith, Ms."                →  suffix="Ms."
  "Smith, Ms. Jane"           →  title="Ms."
  ```

---
**Signal:** neighbor: whether the part after a family comma holds a name word
**history:** decisions/C8 · **implemented:** nameparser/_pipeline/_comma.py
