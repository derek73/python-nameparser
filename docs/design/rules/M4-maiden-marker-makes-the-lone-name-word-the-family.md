# M4 — a maiden marker makes the lone name word the family

**When:** a maiden name has been read out of a name and one name word is left beside it, as in "Smith née Jones".

**Then:** a maiden name standing beside exactly one name word makes that word the family name, whatever suffix or nickname stands beside it, an annotation beside the name being no part of the name, which is how H1 reads the same shape.

- **How the maiden name was written does not enter into it:** a marker taking the words after it (M2), a marker-led clause (M3), and a clause in a pair the caller declared to mean maiden (M1) announce the same thing, and the last of those carries no marker at all.
  ```
  "Smith (née Jones)"         →  family="Smith"
  "Smith (Jones)"  maiden-parens  →  family="Smith"
  ```
- **Where the maiden name stood does not matter, only what is left beside it:** a marker inside the name takes the rest of it (M2), and one name word left that way is one name word.
  ```
  "Jane née Jones Smith"      →  family="Jane"
  ```
- **A nickname holds nothing off:** where N3 has already named the family this rule finds nothing left to move, and where N3 declined — its count does not set a suffix aside — this rule names it.

**Because:** a maiden name is a FORMER family name, and nobody announces the surname they used to carry where there is no surname beside it to tell it apart from. So the one name word left standing is the surname the bearer uses now, and writing the clause at all is what rules out the given-name reading O5's convention would otherwise leave it with.

```
"Smith née Jones"           →  family="Smith"
"Smith née Jones PhD"       →  family="Smith"
```

**Except:**

- **A word the vocabulary has claimed as a given name keeps that reading, and so does a word read as an initial** (T4, T5), which is nobody's family name. Both are beyond the rule's reach for one reason: it changes what POSITION would have decided, so it cannot overrule what a word already IS (mechanisms.md#TWO-LAYER-ASSIGN).
  ```
  "abd née Jones"             →  given="abd"  · boundary
  "J. née Jones Smith V"      →  given="J."  · boundary
  "j nee smith"               →  given="j"  · boundary
  ```

**Precedence:**

- **A name carrying a TITLE** is H1's rather than this rule's, H1's given-name-title carve-out included, which keeps the word a given name.

---
**Signal:** count
**history:** decisions/M4 · **implemented:** nameparser/_pipeline/_post_rules.py
