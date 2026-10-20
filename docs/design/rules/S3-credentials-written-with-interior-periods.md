# S3 — credentials written with interior periods

**When:** a word written with interior periods stands in a name, as in "John Smith Msc.Ed.".

**Then:** a word with interior periods reads as a suffix when any of its period-separated chunks is suffix vocabulary, and a word of two or more period-separated chunks that no vocabulary claims is read by POSITION instead, as a bare ambiguous acronym is (S4).

- **An ambiguous acronym written with its periods**, one after each letter or one after each of two or more letter chunks, counts unambiguously; a single trailing period is the abbreviation shape any word can wear and does not. Written so, it is not the bare acronym S4 counts words to spare for: the periods are how a credential is written and a name is not.
  ```
  "John Smith M.A."           →  suffix="M.A."
  "Wang M.Eng."               →  suffix="M.Eng."
  ```
- **A word no vocabulary claims, read by position**, is a credential where the name has words to spare, a name word where it does not, either reading reported at the slots S4 reports at, and the same at a comma — which means the FIRST piece after a family comma, the word trailing the given part after one, the word ending a maiden marker's clause (M2), and the part before a SUFFIX comma. The part before a FAMILY comma never reports, the comma having already named it the family.
  ```
  "John Smith J.u.n.i.o.r."   →  suffix="J.u.n.i.o.r."
  "John Smith Q.W.E.R.T."     →  suffix="Q.W.E.R.T."
  "John Smith X.Y.Z."         →  suffix="X.Y.Z."
  "Doe, John X.Y.Z."          →  suffix="X.Y.Z."
  "Jane Doe nee Smith X.Y.Z." →  suffix="X.Y.Z."
  ```
- **What the position reading reads.** Case says nothing here — the periods are the evidence — and three shapes are outside it: a single trailing period is not this shape at all, a chunk that is not wholly alphabetic is no acronym letter, and a word carrying a script that writes no abbreviations is not wearing an abbreviation's periods (H2 refuses the same word for the same reason).
  ```
  "john smith x.y.z."         →  suffix="x.y.z."
  "John Smith 1.4"            →  family="1.4"  · boundary
  ```

**Because:** credentials are often written run together with periods, and the chunks between the periods are what carry the vocabulary. A word of several chunks that no vocabulary knows is still written the way a credential is written. An acronym that is also an ordinary name is unmistakably a credential when its periods are written.

```
"John Smith Msc.Ed."        →  suffix="Msc.Ed."
"Doe, John Msc.Ed."         →  suffix="Msc.Ed."
"Jack Ma."                  →  family="Ma."  · boundary
"John Smith Xyz."           →  family="Xyz."  · boundary
```

**Except:**

- **Every chunk the vocabulary matches is a single ASCII character**, the roman numerals and the lone digit the vocabulary lists, which are about generations rather than credentials: those chunks do not make the word a suffix.
  ```
  "Jack X.Y.I."               →  family="X.Y.I."  · boundary
  ```
- **The position reading is a caller switch, ON by default**, and the example lines name it; turned off, such a word is name material and the chunk rule still decides the rest.
  ```
  "John Smith X.Y.Z."  unlisted_dotted_suffixes-off  →  family="X.Y.Z."
  "John Smith Msc.Ed."  unlisted_dotted_suffixes-off  →  suffix="Msc.Ed."
  ```

**Precedence:**

- **Paired initials at the first slot after a comma** ("García Márquez, G.J."): they read as the given name unless something in the part speaks for them (C5).
- **A flip to the credential run at the first slot after a comma** ("John Smith, X.Y.Z."): where no listed member of the class takes part it is not reported, unless paired initials speak only for each other (C11).

**Accepted:**

- The initialless-script clause carries no example line of its own. Every input that exercises it composes a script that writes no abbreviations with a period that only a Latin convention writes — `John Smith 田.中.` is the shape — and a composed form no writing system produces is tolerated input rather than contract, which an example of a normative rule would promise. So the witnesses are the tolerated row tests/v2/cases.py's an_initialless_script_glued_into_periods_is_not_this_shape and the CJK assertions in tests/v2/pipeline/test_vocab.py's test_period_joined_vocab_retires_the_single_character_chunk. W3 states the same precedence for the same reason.

---
**Signal:** shape: a word with interior periods, read by its chunks or as the acronym its letters spell
**history:** decisions/S3 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
