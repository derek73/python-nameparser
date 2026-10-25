# S11 — a suffix word that is also a name

**When:** a generation word that is also borne as a name stands where a suffix may stand, as in "Pedro Alves Neto" or "Alexandre Dumas fils".

**Then:** it reads as the generation only where the name has words to spare, as a bare ambiguous acronym does (S4), and at the slots that report, either reading carries the ambiguity flag.

- **The writing is read by S6**, and for a generation word such as French `fils` it speaks at the other end of the case: lower case in a name of mixed case is the generation, Title case leans to the name, capitals say nothing. The floor holds first: lower case settles it only where the name keeps a family word, so two name words keep the family, and so does a part after a comma with no name before it. An agnomen, the Portuguese `Filho`, `Neto`, `Sobrinho` and their feminines, is written in the case of the name around it, so its writing never speaks and the count decides alone.
- **Only name words in front of it count**: a word there that the trailing run takes, a suffix word, a roman numeral read as the generation (S10), a member of the ambiguous class its writing makes a suffix (S6) or one such a word carries in front of it (S7), is no word to spare, and a suffix word there is no company either, as it is for an acronym (S7).
- **After a comma** the word is read as a member of the ambiguous class is: by the count of the name words before the comma at the first slot after it (C4), and by its writing alone where it ends the given part after a family comma (S5).

**Because:** an agnomen marks its bearer against a relative of the same name, as Junior does, so it ends the name the way a generation does and is not part of the surname the family shares. But `Neto`, `Fils` and `Neta` are borne as names too, and a name of two words has no word to spare for a generation. Case tells a French surname from its generation word, and it cannot tell an agnomen, which takes the case of whatever it is written beside.

```
"Pedro Alves Neto"          →  family="Alves"
"Pedro Alves Neto"          →  suffix="Neto"
"Pedro Alves Neto"          →  ambiguities=("suffix-or-name",)
"PEDRO DA SILVA FILHO"      →  suffix="FILHO"
"Pedro Alves Neto, PhD"     →  suffix="Neto, PhD"
"Pedro Alves Neto Júnior"   →  suffix="Neto Júnior"
"Alexandre Dumas fils"      →  suffix="fils"
"Alves, Pedro Neto"         →  suffix="Neto"
"Ana Neto"                  →  family="Neto"  · boundary
"Ana Neto"                  →  ambiguities=("suffix-or-name",)  · boundary
"PEDRO FILHO"               →  family="FILHO"  · boundary
"Silva, Neto"               →  given="Neto"  · boundary
"Marie Fils"                →  family="Fils"  · boundary
"Pedro Junior Filho"        →  family="Filho"  · boundary
", Dr. fils"                →  family="fils"  · boundary
"PEDRO JUNIOR FILHO"        →  family="FILHO"  · boundary
"Pedro VI Filho"            →  family="Filho"  · boundary
"Pedro MA Filho"            →  family="Filho"  · boundary
"Pedro Junior Ma Filho"     →  family="Filho"  · boundary
"Pedro Alves Junior Filho"  →  suffix="Junior Filho"
```

**Except:**

- **Glued behind an initial** with a period between, the word is part of that one word and is weighed only by the shape the joined word wears (S3), as it was before the word was listed: the name word it is with no word to spare, the dotted credential shape with words to spare.
  ```
  "Pedro M.Filho"             →  family="M.Filho"
  "Pedro Alves M.Filho"       →  suffix="M.Filho"
  ```

**Precedence:**

- **Written case in a mixed-case name** ("Marie Fils", "Dumas fils"): a generation word's Title case outranks the count, as an acronym's does (S6), while its lower case gives way to the floor, a name keeping its family word; an agnomen has no case to weigh.
  ```
  "Jean Marie Fils"           →  family="Fils"
  "Dumas fils"                →  family="fils"
  "Pedro Junior fils"         →  family="fils"
  "Pedro Alves NETO"          →  suffix="NETO"
  ```

**Accepted:**

- A name word standing straight before it counts as a name word whatever it is, so an initial there is left as the family name and a particle there as a family name of its own, as with an ambiguous acronym. An initial before an agnomen most often abbreviates the surname it follows.
  ```
  "Pedro J. Neto"             →  family="J."
  "Pedro de Neto"             →  family="de"
  ```
- A three-word name whose last word is a surname that is also an agnomen loses that surname to the suffix, reported, as `Ruth Ann Neta` does. A register whose filer typed the agnomen alone in the surname box disagrees with the reading, and one whose filer typed it after the surname before it agrees.
  ```
  "Ruth Ann Neta"             →  suffix="Neta"
  ```

---
**Signal:** count: name words to spare beside a generation word that is also a name
**history:** decisions/S11 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
