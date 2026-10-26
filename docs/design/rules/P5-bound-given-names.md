# P5 — bound given names

**When:** a recognized bound given-name word stands in a name with a word after it, as in "abdul salam ahmed salem".

**Then:** a recognized bound given-name word joins the word after it into one given name, where the name has a name word to spare or a family comma or a given-name title has lifted that need (below).

- **It needs a name word to spare**, so two name words alone do not join — the second is the family name — except after a family comma, where the family is already fixed, or after a given-name title, which asserts that a given name follows (H1): there the two words join and the name has no family — two name WORDS, so neither a particle chain (P2), which is the family name, nor a suffix word is joined. A run of several titles is read as H1 reads it, by the title that does the addressing, which is its last.
  ```
  "abd Allah"                 →  given="abd"
  "Abu Bakar"                 →  given="Abu"  · boundary
  "Dr. abdul salam"           →  family="salam"  · boundary
  "Salam, abd Allah"          →  given="abd Allah"
  "Sheik abdul salam"         →  given="abdul salam"
  "Sheik abdul salam Jr"      →  given="abdul salam"
  "Sir abdul van der Berg"    →  family="van der Berg"  · boundary
  "Sheik abdul Jr Smith"      →  given="abdul"  · boundary
  ```
- **What there is to spare is what the name's trailing reading leaves**: the trailing suffix run (S2) and the trailing title run (H5), each read over what the other leaves until neither takes anything more, are read once, before the join is tried, and the name words they leave are the words to spare. A trailing roman numeral the run takes (S10), or a bare acronym it takes, or a trailing title word the run takes, is no word to spare; a bare ambiguous acronym is a name word wherever the peel does not take it. The join joins two name words into one and, read after the trailing run, changes no suffix reading: a word the run left as a name word stays one, whatever the join makes of the word in front of it.
  ```
  "abdul Smith V"             →  family="Smith"
  "abdul Smith V"             →  suffix="V"
  "abdul Smith Jr V"          →  family="Smith"
  "abdul Smith Jr Ma"         →  given="abdul"
  "abdul Smith Jr Ma"         →  suffix="Jr Ma"
  "abdul Smith Ma"            →  given="abdul Smith"
  "abdul Smith Berg Ma"       →  middle="Berg"  · boundary
  ```
- **The marker and the words it will take are not among the words to spare**: they leave the name, so counting them asks the question about a name that will not exist. A marker left as a word that a particle join (P2) has already taken travels with that join.
  ```
  "abd Berg née Jones"        →  family="Berg"
  "abd Allah Smith née Jones" →  given="abd Allah"
  "abd née Jones"             →  given="abd"
  ```
- **After a family comma the family is fixed and the joined pair is the given whatever follows**, so the reserve there reads no peel: the join stands whenever the word after the bound word is a name word.
  ```
  "Berg, abdul Prof. Ali"     →  given="abdul Prof."  · boundary
  ```
- **A title word standing in the name is a name word (H3) and joins like one, and so is a particle the chain has not taken (P2)**: the pair is a given name whatever tag the word carried.
  ```
  "abdul Sir Smith Berg"      →  given="abdul Sir"
  "Berg, abdul van"           →  given="abdul van"
  ```

**Because:** some given-name words are incomplete alone — "abdul" is a bound form that the next word completes.

```
"abdul salam ahmed salem"   →  given="abdul salam"
"mohamad ali smith"         →  given="mohamad"  · boundary
"abdul V Smith"             →  given="abdul V"  · boundary
```

**Except:**

- **The join never absorbs a marker standing as a word of its own** — a marker is not a name word (M2) — nor a word of the unambiguous suffix vocabulary (S2), wherever position will then place it, nor a member of the ambiguous class its capitals settle as the credential in a name of mixed case (S6), nor a credential split across a space (S12) that the given part after a family comma holds, nor a title word a trailing rule reads as a title: one the trailing title run (H5) takes from the given part after a family comma, read as the comma-less name reads it with the bare salutations H8 adds, or any title word in a part past the second comma (C2).
  ```
  "Berg, abdul MA"            →  suffix="MA"
  "Berg, abdul ma"            →  given="abdul ma"
  "abdul Jr Smith Berg"       →  given="abdul"
  "abdul Jr Smith Berg"       →  middle="Jr Smith"
  "abdul Ph. D. Smith Berg"   →  suffix="Ph. D."
  "Rahman, Abdul MB ChB"      →  suffix="MB ChB"
  "Berg, abdul Prof."         →  given="abdul"
  "John Smith, Jr., abdul Dr. Smith"  →  title="Dr."
  "Berg, abd née Jones"       →  given="abd"  · boundary
  ```
- **A particle the chain has not taken that is of the unambiguous suffix vocabulary too (vd, mc)** is declined as the suffix piece it is, though such a particle otherwise joins.
  ```
  "Berg, abdul vd"            →  family="vd Berg"
  ```

**Precedence:**

- **A bound word that is also a particle** ("Abu Bakar Salim"): where the join fires, it is read as the bound word: the join outranks the leading-position reading (P4) and no fork is reported; where the reserve blocks the join, P4's reading and its fork stand.
  ```
  "Sheik Abu Bakar"           →  given="Abu Bakar"
  "Abu Bakar Salim"           →  given="Abu Bakar"
  ```
- **A word that is BOTH bound-given and suffix vocabulary** ("abd Allah Smith", "Smith, Abd"): position decides and both readings survive: leading, it is the bound word; trailing, it is the suffix (S2). In the given slot after a family comma the suffix reading wins.
  ```
  "abd Allah Smith"           →  given="abd Allah"
  "Smith, Abd"                →  suffix="Abd"
  ```
- **A trailing particle after a family comma** ("Berg, abdul van"): the join runs before the trailing particle's attachment (P6) sees the name.

**Accepted:**

- After a family comma the join stands though, unjoined, assign would read the word it takes as the suffix — the family is fixed there and the pair is the given; and a bare ambiguous acronym the peel does not take joins as any name word does.
  ```
  "Berg, abdul V"             →  given="abdul V"
  "abdul Ma Smith"            →  given="abdul Ma"
  ```
- A given-name title plus a bound pair leaves the family empty, as H1 accepts for "Sir John" — the input names no family — under a family-first order too: the join is order-blind, and H1 moves the pair that order placed in the family back to the given name, as it does "Sir John" there.
  ```
  "Sheik abdul salam"         →  family=""
  "Sheik abdul salam"  family-first  →  given="abdul salam"
  "Sheik abdul salam"  family-first  →  family=""
  "Sheik abdul salam"  family-first-given-last  →  given="abdul salam"
  ```
- The given part after a family comma reads the words behind a title by its own walk, and where that walk reads them otherwise than the comma-less name does, the join is declined and no title is read — a shape-only numeral (VI to X), or V before a third comma part, stays a name word there, and a title word that is also a particle is attached by P6 (`Berg, abdul Prof. VI` reads middle 'Prof. VI'; `Berg, abdul St.` reads family 'St. Berg'), each as the same name with an ordinary given word reads.

---
**Signal:** neighbor: a bound given-name word and the name word after it, with a word to spare
**history:** decisions/P5 · **implemented:** nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py
