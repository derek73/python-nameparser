# C12 — a suffix word ending the name before the comma

**When:** the part before the first comma ends in a suffix word — a generation such as Jr. or II, Esq., or an honorific such as Rinpoche, not an acronym — or in a roman numeral the trailing fork reads as the generation (S10), as in "John Smith II, AD".

**Then:** where the words in front of it are a whole name and the name carries the case contrast C6 asks for, the part after the comma is the credential run and the comma a suffix comma.

- **A whole name is counted by C3's count**, in which a title in front is a word, but for a one-letter numeral, which S10 counts without it.
  ```
  "Dr. Smith Jr., AD"         →  suffix="Jr., AD"
  "Smith Jr., John"           →  given="John"  · boundary
  "Jane nee Smith Jr., AD"    →  given="AD"  · boundary
  "Smith VI, AD"              →  given="AD"  · boundary
  "Smith V, AD"               →  given="AD"  · boundary
  "Dr. Smith V, AD"           →  given="AD"  · boundary
  "VI, AD"                    →  given="AD"  · boundary
  "John J VI, AD"             →  given="AD"  · boundary
  ```
- **In that part a title reads as a title**, whether one word or a run of title words a connective joins (P3, C7), a dual inside such a run included, and any other word, a title and suffix dual among them, as a suffix.
  ```
  "John Smith Jr., AD RA"     →  suffix="Jr., AD RA"
  "John Smith Jr., Sir AD"    →  title="Sir"
  "John Smith Jr., Sir AD"    →  suffix="Jr., AD"
  "John Smith Jr., Mr. and Mrs. AD"  →  title="Mr. and Mrs."
  "John Smith Jr., Mr. and Mrs. AD"  →  suffix="Jr., AD"
  "John Smith Jr., AD Sr. and Mr."   →  title="Sr. and Mr."
  ```

**Because:** a generation belongs to the name it ends, so a name written in natural order carries it before the comma and its credentials after ('John J Ingram III, MD'), as it does Esq. or a post-nominal honorific. A listing whose surname takes a generation puts it there too, but a given name follows it, and a given name is written as a name.

```
"John Smith II, AD"         →  given="John"
"John Smith II, AD"         →  suffix="II, AD"
"John Smith Jr., þingmaður" →  suffix="Jr., þingmaður"
"John Smith Jr., MBChB PhD" →  suffix="Jr., MBChB PhD"
"John Smith VI, AD"         →  suffix="VI, AD"
"John Smith V, AD"          →  suffix="V, AD"
"John Smith II, AD"         →  capitalized_forced="John Smith II, AD"
"John Smith II, AD"         →  ambiguities=("suffix-or-name",)
"John Smith, AD"            →  given="AD"  · boundary
```

**Except:**

- **A generation word that is also a name** (S11) is no evidence here, since it may be the surname the family comma names: the part before the comma ends in a name word.
  ```
  "Silva Neto, Pedro"         →  family="Silva Neto"
  "Pedro Alves Neto, AD"      →  given="AD"  · boundary
  ```
- **A word of it written as a name, or an initial, keeps the listing form.**
  ```
  "Lloret Palol II, Josep Antoni"  →  given="Josep"  · boundary
  "Garcia Lopez Jr., Juan"    →  given="Juan"  · boundary
  "John Smith Jr., J."        →  given="J."  · boundary
  "Smith Jones Jr., J.A."     →  given="J.A."  · boundary
  ```

**Precedence:**

- **Paired initials after a generation** ("John Smith Jr., M.J."): written dotted, they keep C5's reading and are the given name, the generation staying the suffix; undotted as two capitals, they are this rule's credential (C1, where the roman numerals S10 reads stay the suffix as the listed ones do).

**Accepted:**

- Initials written without periods after the generation read as the credential they look like, a word of two capitals being both; written with them they are initials, as C5 reads them.
  ```
  "Lloret Palol II, JA"       →  suffix="II, JA"
  ```
- A name written in one case, or in a script without case, has no contrast to read and keeps the listing form, as C6's unlisted all-caps word does.
  ```
  "JOHN SMITH JR, AD"         →  given="AD"  · boundary
  ```

---
**Signal:** neighbor: a generation or honorific word ending the part before the comma
**history:** decisions/C12 · **implemented:** nameparser/_pipeline/_comma.py
