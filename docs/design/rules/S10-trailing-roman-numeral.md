# S10 — the trailing roman numeral

**When:** a roman numeral stands in a name's trailing run — ending the name, or with other suffix words behind it — as in "John Smith III" or "John Smith VI MD".

**Then:** the numeral reads as the generation: the numerals the vocabulary lists, and those up to X it does not, by their shape alone.

- **Wherever it stands in the run, in two or more letters.** A numeral of two or more letters with a credential or another suffix word behind it reads as one ending the name does, so every such spelling joins the run as the listed ones always have.
  ```
  "John Smith VI MD"          →  suffix="VI MD"
  "John Smith III MD"         →  suffix="III MD"
  "Jane Doe nee Smith VI PhD"  →  suffix="VI PhD"
  ```
- **A numeral of two or more letters keeps its reading written with a period**, as the German ordinal writes one, the listed numerals reading so too.
  ```
  "Georg VI."                 →  suffix="VI."
  "Konstantin VII."           →  suffix="VII."
  ```
- **What reports.** A numeral of one letter reports whichever way the words-to-spare count reads it: either reading is reported, as either reading of an ambiguous acronym is. A numeral read by its shape alone reports too; a numeral the vocabulary lists in two or more letters is not in question and reports nothing.
  ```
  "John Smith V"              →  ambiguities=("suffix-or-name",)
  "John V"                    →  ambiguities=("suffix-or-name",)
  "John Smith VI"             →  ambiguities=("suffix-or-name",)
  "John Smith VI MD"          →  ambiguities=("suffix-or-name",)
  "John Smith III"            →  ambiguities=()
  ```
- **Written case settles the fork one way:** a numeral written in lower case in a name of mixed case is the generation and reports nothing, being no initial there (T4).
  ```
  "John Smith vi"             →  ambiguities=()
  ```
- **And leans it the other:** a Title-case numeral in a name of mixed case leans to the name, as a Title-case member of the ambiguous class does (S6), and reports, the fork having weighed it.
  ```
  "Nguyen Van Vi"             →  family="Van Vi"
  "Nguyen Van Vi"             →  ambiguities=("suffix-or-name",)
  "John Smith Vi"             →  family="Vi"
  ```
- **A name written wholly in one case says nothing about any letter in it** (T4).
  ```
  "JOHN V"                    →  family="V"
  "john v"                    →  family="v"
  "john smith v"              →  ambiguities=("suffix-or-name",)
  "john smith i"              →  ambiguities=("suffix-or-name",)
  "JOHN SMITH VI"             →  suffix="VI"
  ```
- **A marked letter (P8) that is such a numeral reports this way and not as a connective.**
  ```
  "john i"                    →  family="i"
  "john i"                    →  ambiguities=("suffix-or-name",)
  "john i dr."                →  ambiguities=("suffix-or-name",)
  ```

**Because:** a roman numeral ending a name is its generation, and the post-nominals written after the generation do not change what it is. But one letter is also how an initial is written. A name of two words has no word to spare for it.

```
"John Smith V"              →  suffix="V"
"John W. Ingram V"          →  suffix="V"
"John W Ingram V"           →  suffix="V"
"John Ingram V"             →  suffix="V"
"John Smith VI"             →  suffix="VI"
"John III"                  →  suffix="III"
```

**Except:**

- **A numeral of one letter needs words to spare**, as a bare ambiguous acronym does (S4): as the second of two name words it is the family name, a title in front being no word to spare.
  ```
  "John V"                    →  family="V"
  "Malcolm X"                 →  family="X"
  "Dr Smith V"                →  family="V"
  "John V, Dr."               →  family="V"
  ```
- **An initial in front makes it a name word too.** When the word in front of the numeral is written as an initial, the numeral is a name word, unless the vocabulary lists it in two or more letters; in a name written wholly in one case a bare letter in front is written as one (T4).
  ```
  "John J. V"                 →  family="V"  · boundary
  "John J. VI"                →  family="VI"  · boundary
  "John J. III"               →  suffix="III"
  "john j v"                  →  family="v"
  ```
- **A single letter written with a period is an initial** (T5).
  ```
  "John Smith V."             →  family="V."  · boundary
  ```
- **A numeral past X is a name word.**
  ```
  "John Smith XI"             →  family="XI"  · boundary
  "John Smith XI MD"          →  family="XI"  · boundary
  ```

**Precedence:**

- **Before a suffix comma** ("John Smith V, PhD"): a numeral ending the part before the comma is read by this rule, and C12 says when it makes the comma a suffix comma. Written case is asked of the whole name, the credential after the comma included, so a part written in lower case before a capitalized credential belongs to a name of mixed case: its lower-case numeral is the generation and reports nothing, and a bare lower-case letter in front of it is no initial (T4).
  ```
  "john smith v, PhD"         →  ambiguities=()
  "john j v, PhD"             →  family="j"
  ```
- **Before a family comma** ("John Smith V, M.J."): a numeral ending the family part is read by this rule, its words to spare counted in that part (C1). Only a generation its shape alone reads reports there; a numeral the comma leaves in the family name is silent, the comma having named the family.
  ```
  "Smith VI, John"            →  suffix="VI"
  "Smith VI, John"            →  ambiguities=("suffix-or-name",)
  "Smith V, John"             →  family="Smith V"
  "Smith V, John"             →  ambiguities=()
  "Smith Vi, John"            →  ambiguities=()
  ```
- **In the given part after a family comma** ("Smith, John VI"): the given part is not counted, the comma having settled the count there (S5), and no initial in front is asked. A numeral of two or more letters reads as the generation, reporting where its shape alone reads it, save a Title-case one in a mixed-case name, which stays a name word in silence; a one-letter numeral is the generation only where the vocabulary lists it and it ends the part (C9), so an unlisted one stays the middle initial.
  ```
  "Smith, John VI"            →  suffix="VI"
  "Smith, John VI MD"         →  suffix="VI MD"
  "Smith, John V"             →  suffix="V"
  "Smith, John X"             →  middle="X"
  "Smith, John V MD"          →  middle="V"
  "Smith, John Vi"            →  middle="Vi"
  "Smith, John Vi"            →  ambiguities=()
  ```

**Accepted:**

- A numeral of one letter with another suffix word behind it is not the last word of the name and is read as any word there is, so a one-letter numeral before a credential is the family name, and the reading is reported, as either reading of the fork is, whether the credential is written as one word or split across two (S12). A lone letter there abbreviates a surname as often as it numbers a generation.
  ```
  "John Smith V PhD"          →  family="V"
  "John Smith V PhD"          →  ambiguities=("suffix-or-name",)
  "John Smith V Ph. D."       →  family="V"
  "John Smith V Ph. D."       →  ambiguities=("suffix-or-name",)
  "john i phd"                →  ambiguities=("suffix-or-name",)
  "Jane Doe nee Smith V PhD"  →  ambiguities=("suffix-or-name",)
  ```
- A generation written in Title case in a mixed-case name reads as a name word, the lean that keeps a surname such as 'Vi' a name taking it too.
  ```
  "John Smith Viii"           →  family="Viii"
  ```
- A numeral the vocabulary lists in two or more letters is not weighed: an initial in front does not make it a name word, nor does Title case lean it to the name, the vocabulary settling it as it settles any unambiguous suffix word. No one writes 'III' as an initial or bears 'Ii' as a name.
  ```
  "John Smith Iii"            →  suffix="Iii"
  ```

---
**Signal:** shape
**history:** decisions/S10 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
