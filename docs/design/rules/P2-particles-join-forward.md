# P2 — particles join forward

**When:** a particle stands inside a name with name words after it, as in "John van der Berg".

**Then:** a particle joins the words after it into one name part, the join running until the next particle starts a group of its own, a trailing suffix begins, a maiden marker takes the words after it (M2), or the name ends; the final group reads as the family name, and earlier groups read by position.

- **The chain begins wherever the name begins**, and a preceding title does not move that point (P4).
  ```
  "Dr. John van der Berg"     →  family="van der Berg"
  ```
- **Where a trailing suffix begins** is the trailing run S2 reads, once, before the chain is made and counting the chain's own run as the one name word it will be, so the chain cannot change what it counts: a trailing roman numeral S10 reads as the generation, or a bare acronym with words to spare, ends the chain as a suffix word does, and so does a bare ambiguous acronym written in capitals in a mixed-case name (S6), which needs no words to spare. In the given part after a family comma such a member ends the chain wherever it stands, since the run S8 starts behind the given word takes it and every word behind it; elsewhere a member the trailing read does not take stays the chain's.
  ```
  "Smith, Freiherr von Berg MA Jones"  →  given="von Berg"
  "Freiherr von Berg MA Ma"   →  family="von Berg MA Ma"  · boundary
  "John van der Berg PhD"     →  family="van der Berg"
  "John van der Berg V"       →  family="van der Berg"
  "John van der Berg V"       →  suffix="V"
  "john van der berg ma"      →  suffix="ma"
  "John van der J. V"         →  family="van der J. V"  · boundary
  "Freiherr von Berg MA"      →  family="von Berg"
  "Freiherr von Berg MA"      →  suffix="MA"
  "Freiherr von Richthofen V" →  family="von Richthofen V"  · boundary
  ```
- **The same acronym written Title-case in a mixed-case name ends nothing** and joins the chain as any name word does, words to spare or not, and the fork the chain called is reported there exactly as it is where no particle stands (S4).
  ```
  "John van der Berg Ma"      →  family="van der Berg Ma"
  "John van der Berg Ma"      →  ambiguities=("suffix-or-name",)
  ```
- **Where P1's fold has claimed the opening, the fold decides the family instead** — and may take only PART of the final group, since it counts name words and the group is one part.
  ```
  "de la Cruz Juan Carlos"  family-first  →  family="de la Cruz"
  ```

**Because:** a particle is written as part of the surname it precedes, and a title stands outside the name entirely.

```
"John van der Berg"         →  family="van der Berg"
"John van der Berg Smith"   →  family="van der Berg Smith"
"Vincent van Gogh van Beethoven"  →  middle="van Gogh"
"Juan de"                   →  family="de"  · boundary
"John van der Berg née Jones"  →  family="van der Berg"
```

**Accepted:**

- A particle of the unambiguous suffix vocabulary too (vd, mc) is a suffix piece to the peel, so where it opens the trailing run the chain stops before it as before any suffix word, and the peel takes it; where it continues a prefix run, the run takes it as a particle, as P6 reads it after a comma — and there the chain reports nothing, the particle reading being P6's fork rather than S4's.
  ```
  "John Smith Mc V"           →  suffix="Mc V"
  "John van Mc"               →  family="van Mc"
  ```
- The same carve-out covers `do`, the one word that is both a particle and an AMBIGUOUS credential acronym: where a particle run takes it, the word is the run's and the chain reports nothing, whatever case it is written in — so `Anh van Do` is silent where `Anh Do`, with no particle standing, reports. A word that is both belongs to the particle run and to P6's fork, not to S4's.
  ```
  "anh van do"                →  family="van do"  · boundary
  "anh van do"                →  ambiguities=()  · boundary
  "Anh van Do"                →  family="van Do"  · boundary
  "Anh van Do"                →  ambiguities=()  · boundary
  ```
- A caller wanting the combined double-surname reading (#132's ask) has it as the surnames view rather than the family field.
  ```
  "Vincent van Gogh van Beethoven"  →  surnames="van Gogh van Beethoven"
  ```

---
**Signal:** neighbor: the words following a particle, up to the next particle, suffix run or marker
**history:** decisions/P2 · **implemented:** nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_post_rules.py
