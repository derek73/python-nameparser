# S3 — credentials written in joined chunks

**When:** a word written in chunks, joined by interior periods or by a hyphen or a slash, stands in a name, as in "John Smith Msc.Ed.".

**Then:** a word with interior periods reads as a suffix when any of its period-separated chunks is suffix vocabulary, a word joined by a hyphen or a slash when every one of its chunks is, and a word of two or more period-separated chunks that no vocabulary claims is read by POSITION instead, as a bare ambiguous acronym is (S4).

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
- **A word joined by a hyphen or a slash** is read by a stricter test than the periods' any: a word whose chunks are joined by a hyphen or a slash reads as a suffix when every chunk counts as a suffix as written, which is to say listed and not a bare member of the ambiguous class (S4), a chunk's own periods counting as they do in a word of its own. One chunk that does not count leaves the word as it would be without this bullet, and a joiner standing alone or glued to one side joins nothing, as do the dash characters other than the hyphen-minus and a split credential's halves (`MD/Ph. D.`).
  ```
  "John Smith, MD/PhD"        →  suffix="MD/PhD"
  "John Smith MD-PhD"         →  suffix="MD-PhD"
  "Smith, John MD/PhD"        →  suffix="MD/PhD"
  ", MD/PhD"                  →  suffix="MD/PhD"
  "John Smith, M.D./Ph.D."    →  suffix="M.D./Ph.D."
  "john smith, ms-pt"         →  suffix="ms-pt"
  "John Smith-Jones, MD-PhD"  →  family="Smith-Jones"
  "John Smith-Jones"          →  family="Smith-Jones"  · boundary
  "Smith, Mary-Jane"          →  given="Mary-Jane"  · boundary
  "John Smith MD-Jones"       →  family="MD-Jones"  · boundary
  ```

**Because:** credentials are often written run together, with periods between their parts or a hyphen or a slash between two of them, and the chunks are what carry the vocabulary. A word of several chunks that no vocabulary knows is still written the way a credential is written. An acronym that is also an ordinary name is unmistakably a credential when its periods are written.

```
"John Smith Msc.Ed."        →  suffix="Msc.Ed."
"Doe, John Msc.Ed."         →  suffix="Msc.Ed."
"John Smith Msc.Ed."  unlisted_dotted_suffixes-off  →  suffix="Msc.Ed."
"Jack Ma."                  →  family="Ma."  · boundary
"John Smith Xyz."           →  family="Xyz."  · boundary
"Ram Bahadur PhD B.K."      →  suffix="PhD B.K."
"สมชาย ใจดี พ.บ."             →  suffix="พ.บ."
```

**Except:**

- **Every chunk the vocabulary matches is a single ASCII character**, the roman numerals and the lone digit the vocabulary lists, which are about generations rather than credentials: those chunks do not make the word a suffix.
  ```
  "Jack X.Y.I."               →  family="X.Y.I."  · boundary
  "Jack I-V"                  →  family="I-V"  · boundary
  "John Smith, MS-V"          →  suffix="MS-V"
  ```
- **Paired initials are the exception**, as C5 defines them, in a script that writes capitals: where S4 would count words to spare for them they are the name word they are written as, as the switch off reads every such word, and the fork is still reported. Two dotted single letters is how initials are written in such a script, and how some surnames are (Nepali B.K., K.C.), while a script without capitals writes its abbreviations that way, degrees among them; behind an unambiguous suffix word the pair joins the credential run that word starts (S8).
  ```
  "Ram Bahadur B.K."          →  family="B.K."
  "Ram Bahadur B.K."          →  middle="Bahadur"
  "Sita Kumari K.C"           →  family="K.C"
  "RAM BAHADUR B.K."          →  family="B.K."
  "Bahadur, Ram B.K."         →  middle="B.K."
  "Ram Bahadur B.K., PhD"     →  family="B.K."
  "Jane Doe nee Smith B.K."   →  maiden="Smith B.K."
  ```
- **The position reading is a caller switch, ON by default**, and the example lines name it; turned off, such a word is name material and the chunk rule still decides the rest.
  ```
  "John Smith X.Y.Z."  unlisted_dotted_suffixes-off  →  family="X.Y.Z."
  ```

**Precedence:**

- **A joined word in capitals with a chunk the stricter test refuses** ("John Smith, MA/PHD"): S9's caps shape reads it, as it reads any unlisted word written in capitals, so after a comma where the name carries C6's case contrast it joins the ambiguous class, where the same word with a lowercase letter stays the name word this rule leaves it.
  ```
  "John Smith, MA/PHD"        →  suffix="MA/PHD"
  ```
- **An ambiguous credential between an unambiguous one and paired initials** ("Jane Doe PhD MA R.T."): the unambiguous word starts the run and the run takes both, the pair included (S8).
- **Paired initials at the first slot after a comma** ("García Márquez, G.J."): they read as the given name unless something in the part speaks for them (C5).
- **A flip to the credential run at the first slot after a comma** ("John Smith, X.Y.Z."): where no listed member of the class takes part it is not reported, unless paired initials speak only for each other (C11).

**Accepted:**

- A joined credential with a chunk that is a bare member of the ambiguous class, written with a lowercase letter, keeps the reading it had before joined chunks were read, where a name in front of a comma is reversed: the hyphen joins names too, and a name word joined to a listed credential is not one the stricter test may take.
  ```
  "John Smith, MA/PhD"        →  given="MA/PhD"
  "John Smith, MA/PhD"        →  family="John Smith"
  ```
- A Korean given name romanized with a hyphen between two syllables the vocabulary lists as unambiguous credentials reads as the credential, unreported after a comma, as its spaced spelling already did: `ae` and `ra` are such credentials, and the hyphen no longer keeps the name a name word.
  ```
  "Kim, Ae-Ra"                →  suffix="Ae-Ra"
  "Kim, Ae Ra"                →  suffix="Ae Ra"
  "Shin Ae-ra"                →  suffix="Ae-ra"
  ```
- An unlisted credential of two letters written with its periods behind a full name reads as the family name, and the reading is reported: King's Counsel, which no vocabulary lists, is the case.
  ```
  "John Smith K.C."           →  family="K.C."
  ```
- Paired initials behind an ambiguous credential that no unambiguous suffix word stands in front of, a listed one or one admitted by its shape (this rule's dotted words, S9's capitals where the caller admits them), end the name and take the credential into it: the reading 1.4.0 through 2.3.0 gave, where a run of credentials is the likelier writing.
  ```
  "Jane Doe MA R.T."          →  family="R.T."
  "Jane Doe MA R.T."          →  middle="Doe MA"
  ```
- The initialless-script clause carries no example line of its own. Every input that exercises it composes a script that writes no abbreviations with a period that only a Latin convention writes — `John Smith 田.中.` is the shape — and a composed form no writing system produces is tolerated input rather than contract, which an example of a normative rule would promise. So the witnesses are the tolerated row tests/v2/cases.py's an_initialless_script_glued_into_periods_is_not_this_shape and the CJK assertions in tests/v2/pipeline/test_vocab.py's test_period_joined_vocab_retires_the_single_character_chunk. W3 states the same precedence for the same reason.

---
**Signal:** shape: a word in chunks joined by interior periods, a hyphen or a slash, read by its chunks or as the acronym its letters spell, and for paired initials whether its script writes capitals
**history:** decisions/S3 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_comma.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
