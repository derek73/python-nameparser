# S11 — a credential split across a space

**When:** a credential stands written as two words, as in "John Smith Pharm. D.".

**Then:** a credential written split across a space reads as one word where its two words are short chunks whose letters together spell unambiguous suffix vocabulary and the two are not both suffix vocabulary on their own, as a member of the ambiguous class (S4) that the count decides as it decides a bare acronym, so that where the count declines it, the pair is the two words it is written as.

- **Which pairs.** Each word is one to five letters, with or without its period, and the first has two or more: a single letter opening the pair is a middle initial far more often than the start of a credential. A particle or a connective written without a period is no chunk of one either, since it joins name words, which is what it is doing beside one.
  ```
  "John Smith Pharm. D."      →  suffix="Pharm. D."
  "John Smith Pharm D"        →  suffix="Pharm D"
  "John Smith Psy. D."        →  suffix="Psy. D."
  "John Smith M. D."          →  family="D."  · boundary
  "Jane Doe de A Junior"      →  family="de A"  · boundary
  ```
- **The count decides.** At the end of a name it needs the words to spare S4 asks of a bare member; after a comma, the name words C4 counts before the comma; ending the given part after a family comma, it reads as S5 reads a member there, its writing saying nothing else.
  ```
  "John Pharm D"              →  family="D"  · boundary
  "John Smith, Pharm D"       →  suffix="Pharm D"
  "Smith, Pharm D"            →  given="Pharm"  · boundary
  "Smith, John Pharm D"       →  suffix="Pharm D"
  ```
- **The run.** Behind two name words where no comma divides the name, or after the given word in the part after a family comma, the pair starts the credential's run (S8) as its one-word spelling does, and a name word the run absorbs reports.
  ```
  "John Smith Pharm D Jones"  →  suffix="Pharm D Jones"
  "Smith, John Pharm D Jones"  →  suffix="Pharm D Jones"
  ```
- **What reports.** The reading itself reports nothing either way: where the count takes the pair its letters spell a listed credential, and where it declines the pair the two words are a given name and an initial, which no reader hesitates over.
  ```
  "John Smith Pharm D"        →  ambiguities=()
  "SMITH, SAM E."             →  ambiguities=()  · boundary
  ```

**Because:** a credential is often typed with a space between its parts, and its letters together are what the vocabulary lists. But two short words are also how a given name and its initial are written, so the pair buys only the ambiguous reading, and the count decides it.

```
"John Smith MB ChB"         →  suffix="MB ChB"
"SMITH, SAM E."             →  given="SAM"  · boundary
"SMITH, SAM E."             →  middle="E."  · boundary
```

**Except:**

- **The Ph./D. pair is an unambiguous credential**, merged wherever it stands but the head of the string and read as a suffix there without the count (decisions/phd-merge), so the count does not decide it; where it overlaps another pair, it is the pair that merges.
  ```
  "John Ph. D."               →  suffix="Ph. D."
  "Jane Doe Dr. Ph. D."       →  title="Dr."
  "Jane Doe Dr. Ph. D."       →  suffix="Ph. D."
  ```
- **Two dotted single letters** in a script that writes capitals are paired initials, which S3 reads as the name word they are written as, and never merge; in a script without capitals they merge where their letters spell listed vocabulary, which no default entry does.
  ```
  "John Smith J. R."          →  family="R."  · boundary
  ```
- **The part before a family comma** reads no member of the class as a suffix, so no pair merges there.
  ```
  "Smith Pharm D, John"       →  family="Smith Pharm D"  · boundary
  ```

**Precedence:**

- **The head of the string** ("Pharm D John Smith"): a suffix never opens the string (S2), so no pair merges there.
  ```
  "Pharm D John Smith"        →  given="Pharm"
  ```
- **A one-letter numeral in front** ("John Smith V Pharm D"): it is the name word S10 reads before any credential, one word or split.
  ```
  "John Smith V Pharm D"      →  family="V"
  ```

**Accepted:**

- A split credential opening with a single letter reads as the two words it is written as, and after a comma behind a whole name the name is reversed around it: `M. D.`, `M D` and `M. Sc.` are written so.
  ```
  "John Smith, M. D."         →  given="M."
  "John Smith, M. D."         →  family="John Smith"
  ```
- A given name and its initial behind two name words, where no comma divides the name, whose letters spell a listed credential read as the credential, in silence: the count reads them as it reads the credential they spell.
  ```
  "JOHN SMITH SAM E."         →  suffix="SAM E."
  ```

---
**Signal:** shape: two short words whose letters together spell a listed credential, decided by the count
**history:** decisions/S11 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_classify.py, nameparser/_pipeline/_comma.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
