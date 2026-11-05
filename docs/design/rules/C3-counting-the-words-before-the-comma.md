# C3 — counting the words before the comma

**When:** the comma's decision (C1) counts the words before the comma, as in "De La Cruz, Ed".

**Then:** a particle run and the one name word it attaches to are one word, the reach P1's fold counts rather than the whole of P2's chain, so 'De La Cruz, Ed' reads as 'Royce, Ed' does and 'van der Berg, PhD' as 'Berg, PhD'.

- **Where that surname is the whole part, the comma settles P1's fork** for a leading particle that could be a given name, being the evidence that the part is a surname.
  ```
  "Van Buren, Ed"             →  family="Van Buren"
  ```
- **A word after the one the particle attaches to is a second word**, and a suffix word ends the particle's reach.
  ```
  "John van Buren, Ed"        →  suffix="Ed"  · boundary
  ```
- **A numeral of two or more letters ending the part is no name word where it reads as the generation**: a numeral ending the part, or standing before the listed suffix words it ends with, that the trailing fork reads as the generation is no name word, as a listed one is not, so a shape-only numeral counts as 'III' does. The fork's writing tests stand (S10), a Title-case numeral in a name of mixed case and one behind an initial staying name words.
  ```
  "Dumas VI, Jr."             →  family="Dumas"
  "Dumas VI, MA"              →  suffix="VI, MA"
  "Dumas VI MD, Ed"           →  family="Dumas"
  "Dumas Vi, Jr."             →  family="Vi"  · boundary
  "Dumas Vi, Ed"              →  family="Vi"  · boundary
  "J VI, Jr."                 →  family="VI"  · boundary
  ```
- **A word that is also title vocabulary is not a particle to this count where it opens the part**, reading there as the title it also is (H1); inside a surname it chains ('de St Pierre, Ed' reads given 'Ed').
- **A connective join and a bound given-name pair are not one word here**: whether P3 joins a connective depends on the words of the whole name, which this count is part of deciding, and a bound given name builds a given name rather than a surname (P5) — a word that is a particle as well counts as the particle ('Abu Bakar, Ed' reads given 'Ed').
  ```
  "Ortega y Gasset, Dr."      →  given="Ortega"
  "Ortega y Gasset, Ed"       →  suffix="Ed"  · boundary
  "abdul Salam, Ed"           →  suffix="Ed"  · boundary
  ```
- **A title in front is a word to the count an unambiguous credential takes**, so 'Dr. van der Berg, PhD' reads as its part does alone.
- **A suffix word opening the part is a name word to the count where a name word follows it**, so the part reads as it does with no comma, where position decides what a word opening the name is (S2). Behind titles it is the first word after them, a word that is a title as well counting as the title it is; a title behind it is no name word ('Md Prof., PhD' keeps its one), and neither is a split credential's member opening the part, being half a credential (S12).
  ```
  "Md Rahman, PhD"            →  given="Md"
  "JP Clancy, MD"             →  given="JP"
  "A.M. Barrett, MD"          →  given="A.M."
  "Cem Akin, Prof."           →  given="Cem"
  "Md Rahman Jr., PhD"        →  given="Md"
  "Dr. Md Rahman, Ing"        →  given="Md"
  "Sr. van der Berg, PhD"     →  given="van"
  "Md, PhD"                   →  family="Md"  · boundary
  "Md Prof., PhD"             →  family="Md Prof."  · boundary
  "Sr. Smith, Ma"             →  given="Ma"  · boundary
  "MB ChB, PhD"               →  family="MB ChB"  · boundary
  "Md Rahman, John"           →  family="Md Rahman"  · boundary
  ```

**Because:** the listing form puts a surname before the comma, and a particle surname is one surname. A word opening the part is a word of the name the writer put there, a given name written short (Md), initials (JP) or a name a credential happens to spell (Cem), and S2 reads it so where no comma follows.

```
"De La Cruz, M.J. K.L."     →  given="M.J."
"De La Cruz, Ed"            →  given="Ed"
"van der Berg, MA"          →  family="van der Berg"
"van der Berg, MA"          →  suffix="MA"
"van der Berg, PhD"         →  family="van der Berg"
```

**Accepted:**

- A numeral of one letter is not set aside: S10 reads it as the generation only where the name has a word to spare for it, and a one-word name has none, so it stays a name word, and the part reads as a given name and a family name rather than the listing form's surname.
  ```
  "Dumas X, Jr."              →  family="X"
  ```
- A title in front of a particle surname, before the credential class's word, reads the listing form. The surname counts once and the title is no name word, so the count reads the listing form, and the listing form peels a title before the comma (H6) unless the word is a particle too, as 'Freiherr' is, which stays in the family. For 'Freiherr' that reading is the right one: since 1919 a former noble title is part of the legal surname, written between the given name and the particle, so 'Freiherr von Berg' is the family name in 'Freiherr von Berg, Ed', as 2.0 through 2.3 read it. A rank that is no particle peels as a title like any other ('Herzog Smith, Anna' reads title 'Herzog'), though the same law makes it part of the surname too; 'Graf' stays, a particle since #709. Before an unambiguous credential the same words keep the title apart ('Freiherr von Berg, PhD'), that count taking the title as a word; both are readings of one name.
  ```
  "Freiherr von Berg, Ed"     →  family="Freiherr von Berg"
  ```

---
**Signal:** count: the words before the comma, a particle surname counting as one
**history:** decisions/C3 · **implemented:** nameparser/_pipeline/_comma.py, nameparser/_pipeline/_vocab.py
