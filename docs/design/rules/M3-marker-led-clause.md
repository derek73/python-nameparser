# M3 — the marker-led clause

**When:** a bracketed clause opens with a recognized maiden marker, as in "Jane Smith (née Jones)".

**Then:** a bracketed clause whose content opens with a recognized marker and carries a word after it reads as the maiden name, whichever bucket the enclosing pair sits in, the marker itself dropped as M1 drops it.

- **Being keyed on the content rather than on the pair, this reaches a nickname pair's clause too** (N1), and M1's independence then governs what it produces: where a marker-led clause stands beside another marker-led clause, both read as maiden and join into one maiden name, leaving no nickname.

**Because:** an enclosure says nothing about whether it means maiden, but a recognized marker word inside it does. The clause announces itself, so the caller does not have to declare the pair.

```
"Jane Smith (née Jones)"    →  maiden="Jones"
"Jane (née Jones) Smith"    →  family="Smith"
"Maria Kowalska (z domu Nowak)"  →  maiden="Nowak"
```

**Except:**

- **A marker with no word after it is just a word in brackets**, and so is a marker no separator divides from the name, the fullwidth-colon spelling M2 records.
  ```
  "Jane Smith (née)"          →  nickname="née"  · boundary
  "Maria Kowalska (z domu)"   →  nickname="z domu"  · boundary
  ```
- **A marker followed by a comma is no marker**, whether the comma stands alone or is glued to either word — here and in M1's drop alike, so a clause the caller declared maiden keeps that marker.
  ```
  "Jane (née , Jones) Smith"  →  nickname="née , Jones"  · boundary
  "Jane (née ,Jones) Smith"  maiden-parens  →  maiden="née ,Jones"  · boundary
  ```

**Precedence:**

- **A pair already configured for maiden names** ("Jane Smith (née Jones)" under a maiden pair): M1 governs and this adds nothing.
- **Suffix-shaped content** ("Jane Smith (née Jr.)"): S1 takes it first, and the clause is no maiden name.
  ```
  "Jane Smith (née Jr.)"      →  suffix="Jr."
  ```

**Accepted:**

- The word taken after the marker is not tested for being a name word, so unlike M2's bare take this one does not stop at a suffix word — the same two words read one way bracketed and another way bare. This does not contradict the S1 example under Precedence: S1 asks whether the WHOLE clause is suffix-shaped, which the trailing period makes true of the one and false of the other, so only V and PhD clauses reach it.
  ```
  "Jane Smith (née V)"        →  maiden="V"
  "Jane Smith (née PhD)"      →  maiden="PhD"
  "Jane Smith née PhD"        →  suffix="PhD"  · boundary
  ```

---
**Signal:** neighbor
**history:** decisions/M3 · **implemented:** nameparser/_pipeline/_extract.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_vocab.py
