# S7 — the company of an unambiguous credential

**When:** a member of the ambiguous class (S4) stands behind an unambiguous credential, as in "John Smith PhD MEng".

**Then:** a member of the ambiguous set standing BEHIND an unambiguous credential in one run of suffix words — members of the class between them passing the run on — reads as the credential whatever its writing and whatever the count, at every trailing slot S4 names: the degree in front says what the run is.

- **Only a credential in front speaks; one behind the member says nothing about it.**
- **What ends the run.** A connective (P3), a particle (P2) — a word of both the particle and the suffix vocabulary heads the family name behind it — and a single-letter roman numeral, in any case — one letter, the shape a bare middle initial is written in, where a multi-letter one such as 'III' speaks — speak for nothing and end the run; so does any name word. A particle of this class standing behind a credential is still spoken for: the exclusion is of the word in front. Where a credential's run starts (S8), a one-letter numeral and a name word behind the credential end the company but not the run ('John Smith PhD V Ma' and 'John Smith PhD Jones Ma' read wholly as suffix). A connective standing between the credential and a word after it is joined to the credential first (P3), so no run starts ('John Smith PhD y Ma' reads family 'PhD y Ma', 'Smith, John PhD and Ma' middle 'PhD and Ma'), except in a part a credential opens after a comma (C13), which is suffix to its end ('Smith, PhD and Ma'); a connective further in is the run's ('John Smith PhD Jones and Ma' reads suffix 'PhD Jones and Ma'), and a letter that is also a roman numeral, such as a mixed-case 'i', reads as the numeral, as a letter P8 reads as an initial is no connective at all.
  ```
  "doe, jane v phd do"        →  suffix="phd do"
  ```
- **A maiden marker's clause.** The company does not reach across a maiden marker's clause (M2), whose name words stand between.
- **What reports.** A member the company decides reports the fork as a counted pick does, wherever it stands: at the trailing slots S4 names, and in a part after a family comma that the company leaves holding no name word, which reads wholly as the credential run. A member its own capitals already made the credential reports nothing new.
  ```
  "Smith, PhD Ma"             →  ambiguities=("suffix-or-name",)
  ```

**Because:** post-nominals are written as a run, and an unambiguous degree in front of an ambiguous member says what the run is.

```
"John Smith PhD MEng"       →  suffix="PhD MEng"
"John Smith PhD Ed Ma"      →  suffix="PhD Ed Ma"
"Wang Ma PhD"               →  family="Ma"  · boundary
"Smith, PhD MEng"           →  suffix="PhD MEng"
"Smith, PhD Ma"             →  suffix="PhD Ma"
"Doe, Jane PhD MEng"        →  suffix="PhD MEng"
```

**Except:**

- **A word of both the title and the suffix vocabulary standing in the given part's leading title run** is a title there and speaks for nothing, and no credential behind it speaks for a word of this class in that part: the title reading makes the next word the given name, and from there the part reads as any given part does, the given part's own company included. A part holding no such word, or only words whose capitals decide them, reads as it did. Anywhere else such a word speaks like any suffix word.
  ```
  "Smith, Ms Ma"              →  given="Ma"  · boundary
  "Smith, RA PhD Ma"          →  given="PhD"  · boundary
  ```

**Precedence:**

- **Against the count and the case** ("John Smith PhD Ed Ma"): company is evidence that outranks both the count (S4) and the case (S6).
- **At the trailing slot of the given part, against the attachment** ("Doe, John PhD Do"): this company outranks P6's attachment, as the capitals do.

**Accepted:**

- A name-leaning member with nothing in front of it to speak for it ends the name, words to spare or not, and whatever stands in front of it is name text. Where a credential does stand in front, the company decides instead. A title standing between the credential and the member, a member a particle chain (P2) had taken, and a credential written split across two words with no comma after the name kept it out of reach until the credential's run (S8) took all three in: the rows a_title_between_degree_and_member_keeps_it_a_name and a_member_the_particle_chain_took_is_out_of_reach keep their ids and now pin the run, and a_split_degree_in_front_starts_the_run pins the third.
  ```
  "Jack Wei Ma"               →  family="Ma"
  "Jack Wei Ma"               →  ambiguities=("suffix-or-name",)
  "abdul Smith Jr Ma"         →  suffix="Jr Ma"
  ```

---
**Signal:** neighbor: an unambiguous credential in front, in one run of suffix words
**history:** decisions/S7 · **implemented:** nameparser/_pipeline/_comma.py, nameparser/_pipeline/_pieces.py
