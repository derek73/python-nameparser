# S10 — the trailing roman numeral

**When:** a name written without a comma ends in a roman numeral, as in "John Smith III".

**Then:** the numeral reads as the generation: the numerals the vocabulary lists, and those up to X it does not, by their shape alone.

- **What reports.** A numeral read by its shape alone reports, as a one-letter numeral does; a numeral the vocabulary lists in two or more letters is not in question and reports nothing.
  ```
  "John Smith VI"             →  ambiguities=("suffix-or-name",)
  "John Smith III"            →  ambiguities=()
  ```
- **Written case settles the fork in one way only:** a numeral written in lower case in a name of mixed case is the generation and reports nothing, being no initial there (T4).
  ```
  "John Smith vi"             →  ambiguities=()
  ```
- **A name written wholly in one case says nothing about any letter in it** (T4).
  ```
  "JOHN V"                    →  family="V"
  "john v"                    →  family="v"
  "john smith v"              →  ambiguities=("suffix-or-name",)
  "john smith i"              →  ambiguities=("suffix-or-name",)
  ```
- **A marked letter (P8) that is such a numeral reports this way and not as a connective.**
  ```
  "john i"                    →  family="i"
  "john i"                    →  ambiguities=("suffix-or-name",)
  "john i dr."                →  ambiguities=("suffix-or-name",)
  ```

**Because:** a roman numeral ending a name is its generation. But one letter is also how an initial is written, and the generation it would name is rare. A name of two words has no word to spare for it.

```
"John Smith V"              →  suffix="V"
"John Smith V"              →  ambiguities=("suffix-or-name",)
"John W. Ingram V"          →  suffix="V"
"John W Ingram V"           →  suffix="V"
"John Ingram V"             →  suffix="V"
"John Smith VI"             →  suffix="VI"
"John III"                  →  suffix="III"
```

**Except:**

- **A numeral of one letter needs words to spare**, as a bare ambiguous acronym does (S4): as the second of two name words it is the family name, a title in front being no word to spare, and either reading is reported, as either reading of an ambiguous acronym is.
  ```
  "John V"                    →  family="V"
  "John V"                    →  ambiguities=("suffix-or-name",)
  "Malcolm X"                 →  family="X"
  "Dr Smith V"                →  family="V"
  "John V, Dr."               →  family="V"
  ```
- **An initial in front makes it a name word too.** When the word in front of the numeral is written as an initial, the numeral is a name word; in a name written wholly in one case a bare letter in front is written as one (T4).
  ```
  "John J. V"                 →  family="V"  · boundary
  "john j v"                  →  family="v"
  ```
- **A single letter written with a period is an initial** (T5).
  ```
  "John Smith V."             →  family="V."  · boundary
  ```
- **A numeral past X is a name word.**
  ```
  "John Smith XI"             →  family="XI"  · boundary
  ```

**Precedence:**

- **Before a suffix comma** ("John Smith V, PhD"): the part before a suffix comma is read as the same name written without the comma (C1).
- **In the given part after a family comma** ("Smith, John V"): the given part is not counted, the comma having settled the count there (S5).

**Accepted:**

- A numeral with another suffix word behind it is not the last word of the name and is read as any word there is, so a one-letter numeral before a credential is the family name, and the reading is reported, as either reading of the fork is.
  ```
  "John Smith V PhD"          →  family="V"
  "John Smith V PhD"          →  ambiguities=("suffix-or-name",)
  "john i phd"                →  ambiguities=("suffix-or-name",)
  "Jane Doe nee Smith V PhD"  →  ambiguities=("suffix-or-name",)
  ```
- A credential written split across two words is read as one with the numeral in front of it, the run taking both, as 1.4.0 read it.
  ```
  "John Smith V Ph. D."       →  suffix="V Ph. D."
  ```

---
**Signal:** shape
**history:** decisions/S10 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
