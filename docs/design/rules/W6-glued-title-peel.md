# W6 — the glued-title peel

**When:** a title is glued directly onto the start of the name's first word, as in "นายสมชาย".

**Then:** a listed title glued to the start of the name's first word splits off once and reads as a title.

- **The first word after a family comma is the name's first word too**, the given part opening there, and a title written apart in front of the word is passed over.
  ```
  "ใจดี, นายสมชาย"                     →  given="สมชาย"
  "รองศาสตราจารย์ นายแพทย์สมชาย ใจดี"  →  given="สมชาย"
  ```
- **The longest listed title is the one split off**, once, so a title that opens with a shorter one keeps its letters.
  ```
  "นางสาวสุดา ใจดี"                    →  title="นางสาว"
  ```

**Because:** a glued word peels off only if it could never open a given name, which the vocabulary marks on the word (attached in front), so the listed vocabulary carries its own license, as W2's does. Thai writes its salutations glued to the given name more often than apart: 35 of the 39 ORCID filers who typed one into the given-name box glued it (2026-11-10).

```
"นายสมชาย ใจดี"                      →  title="นาย"
"นายสมชาย ใจดี"                      →  given="สมชาย"
"อาจารย์สรศักดิ์ ใจดี"                →  title="อาจารย์"
"นายสมชาย ใจดี, Ph.D."               →  given="สมชาย"
"นพพร ใจดี"                          →  given="นพพร"  · boundary
"สมชาย นายใจดี"                      →  family="นายใจดี"  · boundary
```

**Except:**

- **A word the vocabulary lists whole keeps its reading**, though it opens with a title marked to peel.
  ```
  "นายแพทย์สมชาย ใจดี"                 →  title="นายแพทย์"
  "นายแพทย์ สมชาย ใจดี"                →  title="นายแพทย์"
  ```
- **What is left must open as a word can**: where it opens with a Thai vowel written after its consonant, the repetition mark or a mark, the title's letters belong to the word, which stays whole.
  ```
  "นางิ ยานางิ"                        →  given="นางิ"
  "นางาเซะ โทโมยะ"                     →  given="นางาเซะ"
  ```

**Accepted:**

- A title and one name word read as written apart (H1), so the name word is the family name, where Thai writes the given name there.
  ```
  "นายสมชาย"                           →  family="สมชาย"
  ```

---
**Signal:** neighbor: a listed title glued to the start of the name's first word
**history:** decisions/W6 · **implemented:** nameparser/_pipeline/_script_segment.py
