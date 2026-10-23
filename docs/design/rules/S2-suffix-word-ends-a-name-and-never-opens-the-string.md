# S2 — a suffix word ends a name and never opens the string

**When:** a word of the suffix vocabulary stands in a name, as in "John Smith PhD".

**Then:** a trailing word of the suffix vocabulary reads as a suffix — generational forms and credential acronyms alike — and a suffix never OPENS THE STRING, the run's words being read by rules of their own.

- **A word whose period-separated chunks the vocabulary knows, an ambiguous acronym written with its periods, or an unlisted dotted word** is read by S3.
- **A bare ambiguous acronym** is read by S4, S5, S6 and S7.
- **A word joining that class by its shape** is read by S9.
- **A credential with more name text behind it** is read by S8.
- **A roman numeral** is read by S10.

**Because:** generational suffixes and credentials are recognized by vocabulary, and are written after the name they belong to.

```
"John Smith Jr."            →  suffix="Jr."
"Antonio Pavlović mlađi"    →  family="Pavlović"
"Antonio Pavlović mlađi"    →  suffix="mlađi"
"José Silva Júnior"         →  suffix="Júnior"
"Pedro Alves Filho"         →  family="Filho"  · boundary
"Агриппина Младшая"         →  suffix="Младшая"
"جورج بوش الابن"            →  suffix="الابن"
"ロバート・ダウニー・ジュニア"  →  suffix="ジュニア"
"佐藤恵子 国会議員"         →  suffix="国会議員"
"陳子媚 二世"               →  suffix="二世"
"Питер Брейгель мл."        →  suffix="мл."
"Marie Fils"                →  family="Fils"  · boundary
"Jiří Dienstbier ml."       →  family="ml."  · boundary
"Pavlović, Antonio mlađi"   →  suffix="mlađi"
"John Smith PhD"            →  suffix="PhD"
```

**Precedence:**

- **A suffix-shaped word opening the string** ("Ph. D. Van Johnson"): position outranks the vocabulary match, so a suffix-shaped word written before anything else reads as whatever its position and shape make it — a title where it wears the abbreviation shape (H2), an ordinary name word otherwise — and never as a credential belonging to a name that has not been written yet. The string, not the name: a title, a nickname or a bracketed clause standing first leaves the credential reading intact, which is the ONE place this document says "opening" and does not mean what P4 and the H Background mean by it.
  ```
  "Ph. D. Van Johnson"        →  family="Van Johnson"
  "Ph. D. Van Johnson"        →  title="Ph."
  "II Van Johnson"            →  given="II"  · boundary
  "Stariji Bruegel"           →  given="Stariji"  · boundary
  "Sir Ph. D. Van Johnson"    →  suffix="Ph. D."  · boundary
  ```
- **A family comma** ("Smith, Ph. D. Jr.", "Ph. D., John"): a family comma is the other boundary: the comma has already named the family, so a credential run may open the part after it (C13), and the part before it is that family, less a title run opening it (H6).
  ```
  "Smith, Ph. D. Jr."         →  suffix="Ph. D. Jr."
  "Ph. D., John"              →  family="Ph. D."  · boundary
  ```
- **The connectives, the particle chain and the bound given-name join** ("John van der Berg MA"): the run at a name's trailing slot is read ONCE, once the connectives have joined (P3) and before the particle chain (P2) and the bound given-name join (P5) are made, counting a particle run and the name words the chain will take with it as the one name word it will make of them — the words both particles and suffix vocabulary standing straight behind a particle among them, while a word the reading weighs counts as a word of its own wherever it stands; inside a credential run a word stands on its own, a title word there still a title — and neither join reaches a word the run took.
- **A title run in front of a trailing suffix word** ("Dr King Jr"): a title run leaves one NAME word standing and a post-nominal cannot be it (H3), so `Dr King Jr` reads family `King`, suffix `Jr` exactly as this rule states.
- **Written case and the count, at the bare ambiguous acronym** ("Jack MA"): written case outranks the count in a mixed-case name everywhere but the first slot after a comma, where the count decides first (S6, C4); the given part's trailing slot after a family comma is read without the count (S5); and an unambiguous credential in front outranks both (S7).
- **An ambiguous acronym written with its periods** ("Jack M.A."): it counts unambiguously, and is not the bare acronym S4 counts words to spare for (S3).
- **A credential's run against its company** ("John Smith PhD Prof. Ma"): a title standing between the credential and the member, and a member a particle chain (P2) had taken, are the credential's run's (S8), where the company could not reach them (S7); so are a one-letter numeral and a name word, which end the company but not the run. A connective between the credential and a word after it is joined to the credential first (P3), so no run starts, except in a part a credential opens after a comma (C13); one further in is the run's.

**Accepted:**

- A title before the credential keeps it a credential, and behind a title run that addresses by the given name (H1) the name loses its surname exactly as it did before the clause that a suffix never opens the string — `Sir Ph. D. Van Johnson` reads given `Van Johnson` with an empty family. That is 1.4.0's reading, and that clause cannot reach it: the first piece of the NAME is not computable before this decision, since the abbreviation test H2 uses is true of `Ph.` itself, so a scan that stepped over titles would step over the very piece being judged.
- An unambiguous suffix is consumed even when that leaves no family name at all.
  ```
  "Smith Jr."                 →  family=""
  ```
- What the title run's floor (H3) cannot reach stays descriptive and is small: where the run's whole content is the word given back, no title is left to name anybody, so the word stands as the name rather than as the family — `Dr Jr` reads given `Dr`, suffix `Jr`, reporting `title-or-name` (H4), and `Sir Jr` reads by the same branches — given `Sir`, suffix `Jr`, the same kind reported — the run being empty by then and no branch reading `vocab:given-title`. The vocabulary half is decided and unchanged (decisions/v1-xfail-triage: `king` stays a title, for the addressing forms).
  ```
  "Dr Jr"                     →  suffix="Jr"
  ```

---
**Signal:** position: a suffix word ending the name, never opening the string; hub of S3, S4, S5, S6, S7, S8, S9, S10
**history:** decisions/S2 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py
