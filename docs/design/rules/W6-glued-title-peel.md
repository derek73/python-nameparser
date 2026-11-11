# W6 — the glued-title peel

**When:** a title is glued directly onto the start of the name's first word, as in "นายสมชาย".

**Then:** a title the vocabulary marks to peel, glued to the start of the name's first word, splits off once and reads as a title.

- **The first word after a family comma is the name's first word too**, the given part opening there, and a word of listed titles written apart in front of it, alone or joined at their full stops, is passed over, a word holding a name never; the first word before the comma is one, whatever the order makes it, the family name included.
  ```
  "ใจดี, นายสมชาย"                     →  given="สมชาย"
  "รองศาสตราจารย์ นายแพทย์สมชาย ใจดี"  →  given="สมชาย"
  "นายใจดี, สมชาย"                     →  family="ใจดี"
  "รศ.ดร. นายแพทย์สมชาย ใจดี"          →  given="สมชาย"
  ```
- **What is left reads as written apart**: a word still glued at a full stop divides as T8 divides it, before any comma.
  ```
  "อาจารย์ดร.สมชาย ใจดี"               →  given="สมชาย"
  "นางรศ.ดร.สมชาย ใจดี"                →  given="สมชาย"
  "ว่าที่ร.ท.วินัย พืชพิสุทธิ์"             →  title="ว่าที่ร.ท."
  "นางพ.อ.หญิงวาสนา แสงสวย"            →  title="นางพ.อ.หญิง"
  ```
- **A marked title written with its stops** ends where T8 reads its chunk end, past its own full stop or behind a last chunk of two letters or more, and a word that is a listed title whole, stops and all, is passed over written apart.
  ```
  "ใจดี, พล.ต.ต.สุรศักดิ์"              →  given="สุรศักดิ์"
  "ใจดี, พ.อ.หญิงวาสนา"                →  given="วาสนา"
  "พ.อ.หญิง วาสนา แสงสวย"              →  title="พ.อ.หญิง"
  ```
- **The longest marked title is the one split off**, once, so a title that opens with a shorter one keeps its letters; where it would leave a Thai vowel written after its consonant or a mark, the next shorter is tried, and where it is followed by any other character that is no letter, a hyphen, a digit or the repetition mark, nothing is split.
  ```
  "นางสาวสุดา ใจดี"                    →  title="นางสาว"
  "นายแพทย์สมชาย ใจดี"                 →  title="นายแพทย์"
  "นางสาวิตรี ใจดี"                    →  given="สาวิตรี"
  "นางิ ยานางิ"                        →  given="นางิ"  · boundary
  "นางาเซะ โทโมยะ"                     →  given="นางาเซะ"  · boundary
  "นาย-สมชาย ใจดี"                     →  given="นาย-สมชาย"  · boundary
  "นางสาว-สุดา ใจดี"                   →  given="นางสาว-สุดา"  · boundary
  ```

**Because:** a glued word peels off only if it was vetted as opening no name, which the vocabulary marks on the word (attached in front), so the listed vocabulary carries its own license, as W2's does. Thai writes its salutations glued to the given name more often than apart: 35 of the 39 ORCID filers who typed one into the given-name box glued it (2026-11-10).

```
"นายสมชาย ใจดี"                      →  title="นาย"
"นายสมชาย ใจดี"                      →  given="สมชาย"
"นายสมชาย"                           →  given="สมชาย"
"อาจารย์สรศักดิ์ ใจดี"                →  title="อาจารย์"
"นายสมชาย ใจดี, Ph.D."               →  given="สมชาย"
"นพพร ใจดี"                          →  given="นพพร"  · boundary
"สมชาย นายใจดี"                      →  family="นายใจดี"  · boundary
"รองศาสตราจารย์นายแพทย์สมชาย ใจดี"   →  given="นายแพทย์สมชาย"  · boundary
```

**Except:**

- **A title listed whole keeps its reading**, though it opens with a title marked to peel; a title that may be a given name never peels, and a title only in a phrase (H9) peels only with a listed title behind it, which then peels with it where it is marked.
  ```
  "นายแพทย์ สมชาย ใจดี"                →  title="นายแพทย์"
  "ว่าที่สมชาย ใจดี"                    →  given="ว่าที่สมชาย"
  "ว่าที่จ่าสิบตรีสมชาย ใจดี"              →  title="ว่าที่จ่าสิบตรี"
  "ใจดี, ว่าที่ร.ท.วินัย"                →  title="ว่าที่ร.ท."
  ```

**Accepted:**

- One title peels, so a second glued behind it stays with the name ('รองศาสตราจารย์นายแพทย์สมชาย'), Thai writing a title run apart.

---
**Signal:** neighbor: a listed title glued to the start of the name's first word
**history:** decisions/W6 · **implemented:** nameparser/_pipeline/_script_segment.py
