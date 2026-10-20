# T4 — the bare letter as an initial

**When:** a bare letter written in lower case stands in a name, as in "j nee smith".

**Then:** in a name written wholly in one case, which says nothing about any letter in it, a bare letter is an initial wherever its capital would be, and in a name of mixed case a bare lower-case letter is no initial.

- **Every rule that reads an initial differently from a name word reads the lower-case spelling as it reads the capitals**: M4 leaves an initial its given-name reading, O5 reports no convention for one, P3's count passes over one, S10 reads a numeral written as one as the capital numeral it is, and the scan-back of W2's peel, a suffix test that vetoes an initial, vetoes it.
- **A letter whose capital is not an initial by T5** — é, ж — is no initial in either spelling.
  ```
  "é nee smith"               →  family="é"  · boundary
  ```
- **The case question is asked of the name's own words**, as P8 asks it, so a clause beside the name changes nothing about the name's own letters: a lone letter before a maiden name in capitals is still a name written in one case.
  ```
  "j nee Smith"               →  given="j"
  ```
- **A letter outside the name's own words** — in a maiden clause, or past a marker the pass declines (M2) — asks the case of the whole name, the clause included, since the own words' case says nothing of how the clause beside them was written.
  ```
  "dr. née juan y lopez"      →  middle="juan y"
  "DR. NÉE JUAN y LOPEZ"      →  family="JUAN y LOPEZ"  · boundary
  ```

**Because:** a bare letter written in lower case beside capitals is no initial, since nobody writes an initial that way. A name written wholly in one case marks nothing, so its two spellings — all lower case and all capitals — are one name, and read alike.

```
"J NEE SMITH"               →  given="J"
"j nee smith"               →  given="j"
"j"                         →  ambiguities=()
"jose j y lopez"            →  middle="j y"
"smith, j y lopez"          →  given="j"
"john j v"                  →  family="v"
"Jose j y Lopez"            →  family="j y Lopez"  · boundary
```

**Precedence:**

- **A single-letter connective among the name's own words** ("jose e lopez") is P8's question and not this one's: there the vocabulary decides, and the letter it does not mark reads as a connective in both spellings.
  ```
  "jose e lopez"              →  ambiguities=("conjunction-or-initial",)
  "jose y lopez"              →  middle="y"
  ```
- **Under the strict comma-suffix switch** ("john smith, v"): C14's veto refuses the letter the suffix reading wherever it refuses its capital, since the veto asks this rule whether the letter is an initial.

**Accepted:**

- The numeral ending a maiden clause is M2's question, and the take asks the letter in front of it by its own writing alone, so a clause written in lower case can end otherwise than its capitals. Nobody writes an initial straight after a maiden marker, so the shape this reaches is not one names take.
  ```
  "john smith nee x x"        →  suffix="x"
  "JOHN SMITH NEE X X"        →  maiden="X X"
  ```

---
**Signal:** case contrast: a bare letter's case against the name's own words
**history:** decisions/T4 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_vocab.py
