# O5 — the lone name word's convention, and reporting it

**When:** a name has exactly one name word, as in "Smith".

**Then:** a name of one name word that nothing else has decided reads that word as the given name under the default given-first order, and as the family name under a declared family-first one, and carries a `given-or-family` ambiguity naming the field the convention chose.

- **That is a convention rather than a determination** — the same input has to read the same way every time, so one of two equally consistent readings is fixed in advance — and it is not evidence about the word.
- **The report is exactly as narrow as the convention**, so every rule named in Except silences it where it fires, and a family comma — a comma with a name segment after it — silences it too.
- **A comma with nothing after it names no family and silences nothing**, so `سلمان،` and `Smith,` report where `Smith, Andrew` does not.
- **A word with no letter or digit in it is no name word** and reports nothing (A2).

**Because:** O4 reads a name by comparing where its words stand, and a name of exactly one name word gives it nothing to compare — the first name word is also the last, so the rule that decides every longer name is silent here. Nothing in such an input says whether the word is a given name or a family name: both readings fit it equally well, and the library still has to report one.

```
"Smith"                     →  given="Smith"
"Garcia"  family-first      →  family="Garcia"
"Andrew"                    →  ambiguities=("given-or-family",)
"Garcia"  family-first      →  ambiguities=("given-or-family",)
"Juan & Garcia"             →  ambiguities=("given-or-family",)
"Smith Jr."                 →  ambiguities=("given-or-family",)
"'Smitty' Jones Jr."        →  given="Jones"
"'Smitty' Jones Jr."        →  ambiguities=("given-or-family",)
```

**Except:**

- **A title makes the word the family name (H1)**, except a given-name title, which addresses by given name. A comma with only a TITLE after it names no family, but the title still decides the field wherever it stands, so `John III, Dr.` is silent for H1's reason and not the comma's.
  ```
  "Mr. Johnson"               →  family="Johnson"  · boundary
  "Dr. Smith"                 →  ambiguities=()  · boundary
  "Sir John"                  →  given="John"
  "Sir John"                  →  ambiguities=()
  ```
- **Where the one name unit carries title vocabulary** in a word beside the one it places, or is itself title vocabulary left standing by the title peel, the doubt reported is `title-or-name` instead, which H4 and H7 state — so a title silences THIS kind, not every report at the site.
  ```
  "John of Prince"            →  ambiguities=("title-or-name",)
  ```
- **A script whose own convention settles the order (W4)** decides the word's field, and the report is silenced.
  ```
  "毛泽东"                    →  family="毛泽东"
  "毛泽东"                    →  ambiguities=()
  ```
- **A nickname beside the word also makes it the family name (N3)**, except where a suffix stands beside them too, which its count does not set aside, so `'Smitty' Jones Jr.` keeps the convention's reading and its report.
  ```
  "'Smitty' Jones"            →  family="Jones"  · boundary
  ```
- **A maiden name beside the word also makes it the family name (M4)**, except where the vocabulary or the word's own shape has claimed the word already.
  ```
  "Smith née Jones"           →  family="Smith"  · boundary
  "Smith née Jones"           →  ambiguities=()
  ```
- **The word's own claim decides it**: a particle, a bound given name, an initial (T5, T4).
  ```
  "abd née Jones"             →  given="abd"
  "abd née Jones"             →  ambiguities=()
  "j"                         →  ambiguities=()
  ```

**Precedence:**

- **Against every rule that DOES decide such a name**: that rule wins, and each of them carves out a case it declines to decide — where the convention is what is left.

---
**Signal:** count: one name word that nothing else decided
**history:** decisions/O5 · **implemented:** nameparser/_pipeline/_assign.py
