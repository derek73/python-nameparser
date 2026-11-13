# R5 — the case-repair gate

**When:** case repair (R4) is asked of a parsed name, as in "Ronald Macdonald".

**Then:** case repair acts only on a name written entirely in one case, and a name whose words outside the suffix are written in more than one case is kept as it was written, whether that casing is right not entering into it, unless repair was asked for anyway.

- **The suffixes are left out of that test**: a suffix says nothing about how the writer cased the name — III, PhD, Jr. are written that way whatever the name's case — so the test reads every word the parse did not put in the suffix role.
  ```
  "juan garcia III"           →  capitalized="Juan Garcia III"
  "juan garcia PhD"           →  capitalized="Juan Garcia PhD"
  "JUAN GARCIA Jr."           →  capitalized="Juan Garcia Jr."
  "Juan garcia III"           →  capitalized="Juan garcia III"  · boundary
  ```
- **A title is not left out**, and a cased title still holds repair back.
  ```
  "dr. juan garcia III"       →  capitalized="Dr. Juan Garcia III"
  "Dr. juan garcia"           →  capitalized="Dr. juan garcia"  · boundary
  ```
- **The same test is then asked of each suffix on its own**: a suffix written in more than one case is the writer's spelling and is kept as written where repair was not forced; one written in a single case is repaired like any other.
  ```
  "john smith EdD"            →  capitalized="John Smith EdD"
  "juan garcia Iii"           →  capitalized="Juan Garcia Iii"  · boundary
  "john smith EdD"            →  capitalized_forced="John Smith EDD"
  ```

- **A script whose case no writer chooses against the rest of the name makes no contrast**: Georgian writes its capitals only for a whole word set in them, so a Georgian name mixing them with its lower case, or Georgian beside a Latin word in capitals, is in one case as an Arabic name is, and is repaired; a Latin word in Title case beside it keeps the contrast its own letters make.
  ```
  "ჯეკ MA"                    →  capitalized="ჯეკ Ma"
  "ნინო Smith"                →  capitalized="ნინო Smith"  · boundary
  ```

**Because:** mixed case is evidence that the writer cased the name deliberately, and a repair cannot tell a deliberate spelling from a mistaken one. A name written wholly in one case leaves the repair no such evidence to read either way — the writer who always writes lowercase is indistinguishable from the writer who could not be bothered — so repair proceeds there, which is a choice about how to act absent evidence rather than a claim that nothing can be lost by it.

```
"juan mcdonald"             →  capitalized="Juan McDonald"
"RONALD MACDONALD"          →  capitalized="Ronald MacDonald"
"Ronald Macdonald"          →  capitalized="Ronald Macdonald"
"Ronald Macdonald"          →  capitalized_forced="Ronald MacDonald"  · boundary
```

**Accepted:**

- **A Georgian surname written in Mtavruli beside a Mkhedruli given name is written in Mkhedruli**, where a Latin surname written in capitals in a name of mixed case is kept as written: Latin's capitals are case, which a writer chooses against the rest of the name, while Mtavruli is a style of a script with no case, so the name is in one case to the gate and the writer's emphasis is not kept. A Mtavruli first letter on Mkhedruli, written in the Latin habit, is written in Mkhedruli the same way.
  ```
  "ნინო ᲑᲣᲠᲯᲐᲜᲐᲫᲔ"             →  capitalized="ნინო ბურჯანაძე"
  "Უჩა გოგოლაძე"               →  capitalized="უჩა გოგოლაძე"
  "Jean DUPONT"               →  capitalized="Jean DUPONT"  · boundary
  ```

---
**Signal:** case contrast: whether the words outside the suffix are written in one case, a Georgian letter carrying none
**history:** decisions/R5 · **implemented:** nameparser/_render.py
