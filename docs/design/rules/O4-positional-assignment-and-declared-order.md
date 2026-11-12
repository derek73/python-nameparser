# O4 — positional assignment and declared order

**When:** a name word no vocabulary has claimed stands in a name, as in "Mary Beth Smith".

**Then:** words no vocabulary has claimed read by position.

- **In the default given-first order** the first name word is the given name, the last is the family name, and everything between is middle names.
- **In a family-first order** the first name word is the family; in family-first-given-last the given name comes from the end, the middles from between.
- **A name of one name word** is O5's under every order.
- **A name word followed by nothing but initials reports the order**, since the default given-first order read it as the given name where a byline writes the family name first, and a South Asian name writes its letters as the family (O8): one name word, then letters in the shape T5 reads as initials, spaced, or joined by full stops, ending the name words. The report names the word in front as the family as the reading not taken.
  ```
  "Armitage J. O."            →  ambiguities=("order",)
  "Kavitha S"                 →  ambiguities=("order",)
  "Lakshmi R S"               →  ambiguities=("order",)
  "Gomes A.R.S."              →  ambiguities=("order", "suffix-or-name")
  ```

**Because:** what no vocabulary claims can only be read by where it stands, under the order the caller declared.

```
"Mary Beth Smith"           →  middle="Beth"
"Garcia Juan Carlos"  family-first  →  family="Garcia"
"Nguyễn Thị Minh Khai"  family-first-given-last  →  given="Khai"
```

**Except:**

- **A name the order was declared for, or a comma or a switch settles, reports nothing**: a family-first order the caller declared, a family comma naming the family, and `initials_as_family`, which reads the letters as the family (O8).
  ```
  "Armitage J. O."  family-first  →  ambiguities=()
  "Smith, J.O."               →  ambiguities=("suffix-or-name",)
  "Lakshmi R S"  initials_as_family  →  ambiguities=()
  ```
- **What is no name word a byline writes first reports nothing**: a second name word in front (`Ram Bahadur B K`), a run of initials itself (T7), or a word in a script that writes no initials.
  ```
  "Ram Bahadur B K"           →  ambiguities=()
  "J R S"                     →  ambiguities=()
  "John Smith"                →  ambiguities=()
  ```
- **Capitals written as one word with no full stops are no initials here**, being written as a short surname is, so neither the byline nor the surname reports.
  ```
  "Armitage JO"               →  ambiguities=()
  "Zhi LI"                    →  ambiguities=()
  ```

**Accepted:**

- A one-letter numeral read as the family reports the order too, the letter being an initial's shape: `John V` reports both forks it stands in.
  ```
  "John V"                    →  ambiguities=("order", "suffix-or-name")
  ```
- A byline written in bare capitals (`Armitage JO`) is not reported, the cost of not reporting every short capital surname (`Zhi LI`, `Jason NG`) as an order.

---
no-boundary: this is the default reading every other rule carves exceptions from; its boundaries are the other rules.
**Signal:** position: where a word no vocabulary claimed stands, under the declared order
**history:** decisions/O4 · **implemented:** nameparser/_pipeline/_assign.py
