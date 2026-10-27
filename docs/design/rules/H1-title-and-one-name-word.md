# H1 — a title and one name word

**When:** a title or a run of titles stands beside exactly one name word, as in "Mr. Johnson".

**Then:** a title followed by exactly one name word makes that word the family name, whatever suffix, nickname or maiden name stands beside it, unless the title is a given-name title, which keeps it the given name; a run of several titles addresses as its last title does, and where a run stands before the one name word it is the run that addresses, a run standing behind it deciding that word's field only when none stands before.

- **A run written behind the one name word** is the same form of address written on the other side of it, so where no title run stands in front of that word it decides the same reading. Where one does stand in front, that run addresses: a title written behind the name is the name plus that title (H5), and adding it cannot change how the words in front of the name are read.
  ```
  "Smith Sir."                →  given="Smith"
  "Sir John Prof."            →  given="John"
  "Dr. Smith Sir."            →  family="Smith"
  "Dr. Smith II, Sir"  family-first  →  family="Smith"  · boundary
  ```
- **Which side a title is on is decided by the name word** and by nothing else standing beside it, so a run written around a nickname is one run: the name Dr. 'Smitty' Sir John reads as Dr. Sir John does.
- **Neither a comma with nothing but titles after it nor a declared order decides the field.** A comma with nothing but titles after it names no given part, so it says nothing about which field the word before it fills: a comma with no given name after it does not decide the field, nor does a declared order, which places only a word nothing else decided (O5), and the title decides there as it does with no comma.
  ```
  "Elizabeth II, Queen"       →  given="Elizabeth"
  "John III, Sir"             →  given="John"
  "Anne, Swami"               →  given="Anne"
  "Sir John"  family-first    →  given="John"
  "John III, Dr."             →  family="John"  · boundary
  ```

**Because:** a title normally addresses by surname, so a title followed by a single name word usually names the family; but a given-name title addresses by given name. Several titles written together are one form of address, and the one that does the addressing is the last — the words in front of it rank the person rather than name them. What stands beside the name word — a suffix, a nickname, a maiden name — does not make the name any longer, so it does not decide this reading.

```
"Mr. Johnson"               →  family="Johnson"
"Mrs. Garcia"               →  family="Garcia"
"Dr. Smith née Jones"       →  family="Smith"
"Her Majesty Queen Elizabeth"  →  given="Elizabeth"
"Dr. Sir John"              →  given="John"
"His Excellency Lord Duncan"  →  family="Duncan"
"Her Royal Highness Princess Anne"  →  given="Anne"
"Sir John"                  →  given="John"  · boundary
```

**Except:**

- **A particle surname a comma or P1's fold settled keeps the family.** A particle surname standing alone before the comma stays the family, the comma being the evidence that the part is a surname (C3), and so does a never-given particle with a word behind it and no comma (P1's fold).
  ```
  "van der Berg, Sir"         →  family="van der Berg"  · boundary
  "van Gogh, Sir"             →  family="van Gogh"  · boundary
  "Sir de Mesnil"  family-first  →  family="de Mesnil"
  ```

**Accepted:**

- A given-name title plus one name word leaves the family empty — the input names no family, and inventing one would be worse. A run whose last title is a given-name title reads the same way, `queen` doing the addressing where `her majesty` only ranks.
  ```
  "Sir John"                  →  family=""
  "Her Majesty Queen Elizabeth"  →  family=""
  "Smith Sir."                →  family=""
  ```
- A listing record whose given field holds only a given-name title reads that title's reading, so `Smith, Sir` (a row with the given name missing) reads given `Smith` with the family empty, as `Sir Smith` does: the input names one word and one title, and the title is the only evidence there is. 1.4.0 read the word before the comma as the last name in these rows (`Elizabeth II, Queen`, `John III, Sir`, `Smith, Sir`) but for `Anne, Princess`, which it read as first `Anne`. An ambiguous particle no comma settled, or a bare one, is a word the order placed, and reads given.
  ```
  "Smith, Sir"                →  family=""
  "Sheik Abu Bakar"  family-first  →  given="Abu Bakar"
  "Sir de"  family-first      →  given="de"
  "St Sir de Mesnil"  family-first  →  given="de Mesnil"
  ```
- A title word in the run that no vocabulary knows does not change what the run addresses by, the last word being the one asked — `His Excellency Lord Duncan` reads family `Duncan` because `lord` is not a given-name title, not because the run is long. `lord` and `lady` stay out of that list by decision (#519): each addresses by given name only as a courtesy style for children of the senior ranks (`Lord Peter`, `Lady Diana`) and by title or surname for every peer and every wife (`Lord Byron`, `Lady Thatcher`), and the text does not say which the bearer is, which the list cannot express; `prince` and `princess` are in it.
- A title word that is also borne as a name, though rarely as the first word of one (`graf`, `greve`, `herra`), is the title in front of a name, so a name that BEGINS with it -- a surname written first without a comma, or a given name -- gives that word to the title, under a declared family-first order too. Written last without a period, or alone before a family comma, it is the name; a period behind it makes it the title by H5, as for `Mary Jane Pope.` (#606), and a name word behind it before a family comma makes it the title by H6.
  ```
  "Greve Smith, Anna"         →  title="Greve"
  "Greve Anna"                →  family="Anna"
  "Anna Greve"                →  family="Greve"
  "Greve, Anna"               →  family="Greve"
  ```

---
**Signal:** count: exactly one name word beside a title run, read by the run's addressing title
**history:** decisions/H1 · **implemented:** nameparser/_pipeline/_post_rules.py
