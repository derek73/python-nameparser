# P13 — a connective ending the name words

**When:** a connective stands at the end of the name words of the part holding the family name, with at most a lone letter, suffixes or a trailing title behind it, as in "John Smith y V" or "John Smith y III".

**Then:** the connective joins the word before it, and a single-letter connective takes the lone letter behind it too, as the second surname it links.

- **A single-letter connective in front of a lone letter ending the name words joins it to the word before**: the letter, a numeral or an initial, with or without its period, is the second surname written as an initial, P3's three-word carve-out gives way, and a connective that is also generational vocabulary links it too.
  ```
  "John Smith y V"            →  family="Smith y V"
  "Juan García y L."          →  family="García y L."
  "Puig i V, Joan"            →  family="Puig i V"
  "Josep Lluis Carod i V"     →  family="Carod i V"
  "John Smith y V Jr."        →  suffix="Jr."
  "JOHN SMITH Y V"            →  family="SMITH Y V"
  ```
- **A connective with nothing to link joins the word before it alone**: one written as a word, of any length and not also suffix vocabulary, with nothing behind it but suffixes or a trailing title H5 reads, joins the word in front of it and no word after it.
  ```
  "John Smith y III"          →  family="Smith y"
  "John Smith y VI"           →  family="Smith y"
  "John Paul Smith y III"     →  suffix="III"
  "John Smith y"              →  family="Smith y"
  "John Smith and Jr."        →  family="Smith and"
  "John Paul Smith y Prof."   →  title="Prof."
  "محمد علي و"                →  family="علي و"
  ```

**Because:** a connective in a surname links two names, and a lone letter after it is the second written as an initial. One with nothing after it to link stays with the surname it follows, rather than standing alone as the family name or taking a suffix or a title as the name it links.

**Except:**

- **Where the part is the whole name, a word must stand in front of the join past the title run**, so the name keeps a given name, and P3's carve-out stands.
  ```
  "Smith y V"                 →  family="y"  · boundary
  "Dr. Smith y V"             →  family="y"  · boundary
  ```
- **The word before the connective must be a name word**, not a title, a suffix or another connective, so a connective run before a numeral leaves it the generation (S10).
  ```
  "John Dr. y V"              →  family="y"  · boundary
  "Smith y i V, John"         →  suffix="i V"  · boundary
  ```
- **A lowercase letter in a name of mixed case is the generation S10 reads by its writing**, and a capital there is an initial (P8), no connective for this rule to read.
  ```
  "Smith y v, John"           →  suffix="v"  · boundary
  "John Smith Y"              →  family="Y"  · boundary
  ```
- **A connective that is also generational vocabulary, with nothing after it, is the generation it spells** (P3), a symbol connective is no word, and in a name written in one case a single-letter connective with nothing after it keeps its reading, being an initial there as often as a connective.
  ```
  "John Quincy Smith i"       →  suffix="i"  · boundary
  "John Smith & III"          →  family="Smith & III"  · boundary
  "CHENG GUI Y"               →  family="Y"  · boundary
  ```

**Precedence:**

- **Before P3's carve-out**: both joins are made first, so the carve-out never keeps apart a connective this rule joins.
- **Under a family-first order the end of the name is the given name**, which this rule does not read; the part before a family comma is read under every order.
  ```
  "John Smith y V"  family-first  →  family="John"
  "Smith y V, John"  family-first  →  family="Smith y V"
  ```

**Accepted:**

- A name written in one case links a lone letter as its mixed-case twin does: only P8's marked letters read as initials in one case, so a capital `Y` or `И` in front of the letter is the connective this rule reads.
  ```
  "JOHN SMITH Y V"            →  family="SMITH Y V"
  ```

---
**Signal:** neighbor: a connective ending the name words, and the lone letter behind it
**history:** decisions/P13 · **implemented:** nameparser/_pipeline/_group.py
