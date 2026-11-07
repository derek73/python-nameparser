# O5 — the lone name word's convention, and reporting it

**When:** a name has exactly one name word, as in "Smith".

**Then:** a name of one name word that nothing else has decided reads that word as the field the caller's lone-word setting names, the given name unless the caller names the family, under every order, and carries a `given-or-family` ambiguity naming the field the convention chose.

- **That is a convention rather than a determination** — the same input has to read the same way every time, so one of two equally consistent readings is fixed in advance — and it is not evidence about the word.
- **The declared order does not move it**: the order says where a longer name's words stand, and a name of one word stands nowhere relative to another. Which field a word written alone fills is a fact about where the data came from — a list of surnames, a list of the names people go by — so it is the caller's to state, and the given name is the default because a name written alone is more often the one a person goes by.
- **A word that claimed itself is placed the same way**: a bare particle, a bound given name or an initial reports nothing, its own reading having settled what it IS, but nothing in it says which field it fills, so the setting places it too.
- **The report is exactly as narrow as the convention**, so every rule named in Except silences it where it fires, and a family comma — a comma with a name segment after it — silences it too.
- **A comma with nothing after it names no family and silences nothing**, so `سلمان،` and `Smith,` report where `Smith, Andrew` does not.
- **A word with no letter or digit in it is no name word** and reports nothing (A2).

**Because:** O4 reads a name by comparing where its words stand, and a name of exactly one name word gives it nothing to compare — the first name word is also the last, so the rule that decides every longer name is silent here, and so is the order it reads under. Nothing in such an input says whether the word is a given name or a family name: both readings fit it equally well, and the library still has to report one.

```
"Smith"                     →  given="Smith"
"Garcia"  family-first      →  given="Garcia"
"Garcia"  lone_name_word-family  →  family="Garcia"
"Garcia"  family-first+lone_name_word-family  →  family="Garcia"
"de"  family-first          →  given="de"
"Andrew"                    →  ambiguities=("given-or-family",)
"Garcia"  family-first      →  ambiguities=("given-or-family",)
"Garcia"  lone_name_word-family  →  ambiguities=("given-or-family",)
"Juan & Garcia"             →  ambiguities=("given-or-family",)
"Smith Jr."                 →  ambiguities=("given-or-family",)
```

**Except:**

- **A title makes the word the family name (H1)**, except a given-name title, which addresses by given name. A comma with only a TITLE after it names no family, but the title still decides the field wherever it stands, so `John III, Dr.` is silent for H1's reason and not the comma's.
  ```
  "Mr. Johnson"               →  family="Johnson"  · boundary
  "Dr. Smith"                 →  ambiguities=()  · boundary
  "Sir John"                  →  given="John"
  "Sir John"                  →  ambiguities=()
  "Sir John"  lone_name_word-family  →  given="John"
  ```
- **Where the one name unit carries title vocabulary** in a word beside the one it places, or is itself title vocabulary left standing by the title peel, the doubt reported is `title-or-name` instead, which H4 and H7 state — so a title silences THIS kind, not every report at the site.
  ```
  "John of Bishop"            →  ambiguities=("title-or-name",)
  ```
- **A script whose own convention settles the order (W4)** decides the word's field, and the report is silenced.
  ```
  "毛泽东"                    →  family="毛泽东"
  "毛泽东"                    →  ambiguities=()
  ```
- **A nickname beside the word also makes it the family name (N3)**, whatever suffix stands beside them.
  ```
  "'Smitty' Jones"            →  family="Jones"  · boundary
  "'Smitty' Jones Jr."        →  ambiguities=()
  ```
- **A maiden name beside the word also makes it the family name (M4)**, except where the vocabulary has claimed the word as a bound given name or its shape as an initial.
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

**Accepted:**

- A surname written alone under a family-first order reads as the given name unless the caller names the family, as CLDR's `Suzuki-san` does, a surname with a hyphenated honorific CLDR states as the family: the order a caller declares for longer names is not evidence about a word written alone, and a caller whose lone words are surnames says so.
  ```
  "Suzuki-san"  family-first  →  given="Suzuki-san"
  "Anh"  [vi]                 →  given="Anh"
  ```

---
**Signal:** count: one name word that nothing else decided
**history:** decisions/O5 · **implemented:** nameparser/_pipeline/_assign.py
