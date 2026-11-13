# O4 — positional assignment and declared order

**When:** a name word no vocabulary has claimed stands in a name, as in "Mary Beth Smith".

**Then:** words no vocabulary has claimed read by position.

- **In the default given-first order** the first name word is the given name, the last is the family name, and everything between is middle names.
- **In a family-first order** the first name word is the family; in family-first-given-last the given name comes from the end, the middles from between.
- **A name of one name word** is O5's under every order.
- **A name word followed by nothing but initials reports the order**, since the given-first order read it as the given name where a byline writes the family name first, and a South Asian name writes its letters as the family (O8): one name word, then letters in the shape T5 reads as initials, spaced, or joined by full stops, ending the name words, a post-nominal after them being no name word. The report names no alternative, the other reading laying out the whole name (the word in front the family, the letters the given and middle initials) rather than moving one word (A1), and its detail says so, with the setting that reads it (`name_order=FAMILY_FIRST`). The given-first order reports so whether it is the default or declared, the declaration naming the convention, not this name's.
  ```
  "Armitage J. O."            →  ambiguities=("order",)
  "Kavitha S"                 →  ambiguities=("order",)
  "Lakshmi R S"               →  ambiguities=("order",)
  "Gomes A.R.S."              →  ambiguities=("order", "suffix-or-name")
  "PHUOC T DO"                →  ambiguities=("order", "suffix-or-name")
  ```

**Because:** what no vocabulary claims can only be read by where it stands, under the order the caller declared.

```
"Mary Beth Smith"           →  middle="Beth"
"Garcia Juan Carlos"  family-first  →  family="Garcia"
"Nguyễn Thị Minh Khai"  family-first-given-last  →  given="Khai"
"Батын Сүхээ"  [mn]         →  family="Батын"
```

**Except:**

- **A family-first order, a family comma or the switch reports no order**: a family-first order the caller declared, a family comma naming the family, and `initials_as_family`, which reads the letters as the family (O8); any other fork in the name reports as it would.
  ```
  "Armitage J. O."  family-first  →  ambiguities=()
  "Smith, J.O."               →  ambiguities=("suffix-or-name",)
  "Lakshmi R S"  initials_as_family  →  ambiguities=()
  ```
- **What is no name word a byline writes first reports no order**: a second name word in front (`Ram Bahadur B K`), a run of initials itself (T7), a word with no letter, or a word in a script that writes no initials.
  ```
  "Ram Bahadur B K"           →  ambiguities=()
  "J R S"                     →  ambiguities=()
  "12 S."                     →  ambiguities=()
  "王 J"                      →  ambiguities=()
  ```
- **What is no initial ends nothing**: hyphenated initials, which T5 does not tag (`J.-P.`), a transliteration digraph, which H2 reads as a name word (`Yu.`), a one-case letter the vocabulary does not mark as an initial (P8's `Y`), and a Devanagari letter written with a vowel sign (`बि.क.`), which T5 does not read as one letter though it reads a bare one (`राम क.` reports), #1273's question.
  ```
  "Dupont J.-P."              →  ambiguities=()
  "Ivanov Yu. A."             →  ambiguities=()
  "Ivanov Yu."                →  ambiguities=()
  "SILVA Y"                   →  ambiguities=()
  "राम बि.क."                  →  ambiguities=()
  ```
- **Capitals written as one word with no full stops are no initials here**, being written as a short surname is, so neither the byline nor the surname reports.
  ```
  "Armitage JO"               →  ambiguities=()
  "Zhi LI"                    →  ambiguities=()
  ```

**Precedence:**

- **Against a particle in front** (P1's particle-or-given fork): that report names the fork the word in front stands in, so this one stays silent.
  ```
  "Van J. S."                 →  ambiguities=("particle-or-given",)
  ```

**Accepted:**

- A one-letter numeral read as the family reports the order too, the letter being an initial's shape: `John V` reports both forks it stands in.
  ```
  "John V"                    →  ambiguities=("order", "suffix-or-name")
  ```
- A byline written in bare capitals (`Armitage JO`) is not reported, the cost of not reporting every short capital surname (`Zhi LI`, `Jason NG`) as an order.
- A name with no inherited family name reads by position like any other, under the default given-first order its last name word the family: an Ethiopian name, the bearer's own name, the father's and often the grandfather's, gives the grandfather's name as the family where it is written and the father's where it is not, so the same person's family differs between the two spellings. The father's name fills no patronymic view, as rules/R9's Accepted clause says of a patronymic no particle or rule reads.
  ```
  "Abiy Ahmed Ali"            →  family="Ali"
  "Abiy Ahmed"                →  family="Ahmed"
  "Abiy Ahmed Ali"            →  patronymic=""
  ```

---
no-boundary: this is the default reading every other rule carves exceptions from; its boundaries are the other rules.
**Signal:** position + shape: where a word no vocabulary claimed stands, under the declared order; and, for the order report, the count of name words and the initials' written shape (T5)
**history:** decisions/O4 · **implemented:** nameparser/_pipeline/_assign.py
