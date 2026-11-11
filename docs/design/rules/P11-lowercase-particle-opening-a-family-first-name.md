# P11 — a lowercase particle opening a family-first name

**When:** under a family-first order, an ambiguous particle opens the name and has another name word behind it, as in "van den Berg Cornelia".

**Then:** an ambiguous particle written in lower case, in a name of mixed case, opens the name as a never-given one does, P1's fold taking it, its run and one name unit into the family and laying the rest out by the order, and nothing is reported.

- **A capitalized one keeps the reading its position gives it**, the family alone, and is reported (P1's ambiguous particle).
  ```
  "Van Gogh Vincent"  family-first  →  family="Van"
  "Le Van Thanh"  family-first  →  family="Le"
  ```
- **So does one in a name written in one case**, where the writing says nothing.
  ```
  "VAN GOGH VINCENT"  family-first  →  family="VAN"
  ```

**Because:** the order has settled that the opening slot is the family, which leaves the particle one question: is it a one-word surname of its own, or the start of one? The writing answers it, as it answers a connective's (P8): a particle is written in lower case because it joins the word after it, and nobody writes a one-word surname in lower case beside capitals. The family-first surnames that are also particles (Vietnamese `Le`, `Do`, `La`) are written capitalized.

```
"van den Berg Cornelia"  family-first  →  family="van den Berg"
"van Gogh"  family-first  →  family="van Gogh"
"van den Berg Cornelia"     →  given="van"  · boundary
```

**Precedence:**

- **Against H1's given name behind a given-name title**: the writing settles the particle, so it folds there too, H1 reading only a word the order placed; but a bound given name the title licenses P5 to join is one name word, no lone particle, and stays H1's.
  ```
  "Sir van Berg"  family-first  →  family="van Berg"
  "Sir abu Bakar"  family-first  →  given="abu Bakar"
  ```
- **Against P4's title-particle**: a particle that is also a title opens the name as the title, its title reading taken before any particle rule asks about it, so the writing does not reach it.
  ```
  "freiherr von Berg Hans"  family-first  →  title="freiherr"
  "տեր Բրաաք Մենո"  family-first  →  title="տեր"
  ```

**Accepted:**

- A family-first surname that is also an ambiguous particle, written in lower case in a name of mixed case, folds into the family: writing it so is not the convention of any language that writes it, and the capitalized form keeps its reading.
  ```
  "le Van Thanh"  family-first  →  family="le Van Thanh"
  ```
- A capitalized run of two or more particles is not taken as settled, though `Van der Merwe` is one surname: `Le Van Thanh` is the same shape, a family-first surname and a given name.
  ```
  "Van der Merwe Jan"  family-first  →  family="Van"
  ```

---
**Signal:** case contrast: an ambiguous particle opening a family-first name, written in lower case in a name of mixed case
**history:** decisions/P11 · **implemented:** nameparser/_pipeline/_post_rules.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_assign.py
