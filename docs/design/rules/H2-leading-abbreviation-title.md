# H2 — the leading-abbreviation title

**When:** a period-marked word opens the part of the name that carries the given name, as in "Rev. John Smith".

**Then:** an abbreviation opening the part of the name that carries the given name — the whole name, or the part after a family comma — reads as a title even when unlisted, provided it is an unbroken run of two or more letters ending in its one period, the shape outranking vocabulary where it fires, so that a period-marked opening word is a title even when the word is suffix vocabulary, save a credential opening the part after a family comma (C13) and a given name written short.

- **A single-letter initial does not** (T5), and neither does anything with interior periods, hyphens or digits.
  ```
  "J. Smith"                  →  given="J."  · boundary
  "J.R. Smith"                →  given="J.R."  · boundary
  ```
- **A letter written decomposed is the same letter.** An accented Latin, Greek or Cyrillic letter written as a base letter plus a combining mark (NFD) is the same letter as the composed one, for this shape and for the dotted and all-caps credential shapes C5, C6, S9 and S3 read (#652), so such a name parses the same in either encoding and the output keeps the one written.
  ```
  "Dr. inž. Janez Novak"  →  title="Dr. inž."
  ```

**Because:** before a name, an abbreviation is almost always a title — "Rev.", "Ing.", "Mag." — and no vocabulary can list every profession's abbreviations in every language.

```
"Rev. John Smith"           →  title="Rev."
"Xyz. John Smith"           →  title="Xyz."
"Smith, Major. John"        →  title="Major."
"Esq. Smith"                →  title="Esq."
```

**Except:**

- **After a family comma, a part that is nothing but suffix words** is the credential run (C8), which the abbreviation does not open: the vocabulary decides, and "Esq." is the postnominal it is.
  ```
  "Smith, Esq."               →  suffix="Esq."
  ```

**Precedence:**

- **A credential opening the part after a family comma** ("Smith, Esq. John"): C13 wins, and the part is postnominal: a suffix word that starts S8's run makes the part its postnominals however it goes on. The shape still reads as a title there an abbreviation that starts no such run — an unlisted one, or a listed suffix word C13 does not open with, such as a word of the ambiguous class.
  ```
  "Smith, Esq. John"          →  suffix="Esq. John"
  "Smith, Insp. John"         →  title="Insp."
  "Smith, Do. John"           →  title="Do."
  ```
- **A given name written short** ("Chas. Smith", "Ma. Cristina Reyes"): an abbreviation the vocabulary reads as a given name written short is that given name, outranking the shape — traditional English abbreviations such as Chas. and Wm., and the Filipino Ma. (María) and Jo. (José) — so the name reads as it would with the full given name in that place, behind a title too ("Mrs Ma. Liza Cruz"), and C4's count of the name words before a comma, which asks this shape, counts it as one; its period still keeps it out of the case contrast C6 reads, as an initial's does ("Chas. SMITH, XYZ" reads as "J. SMITH, XYZ"). Only the shape yields: a word listed as a title is still one, and written bare, or anywhere but the head of the part that carries the given name, the word reads as it would unlisted, so "Ma" keeps its surname and credential readings.
  ```
  "Chas. Smith"               →  given="Chas."
  "Smith, Chas."              →  given="Chas."
  "Smith, Ma. John"           →  given="Ma."
  "Mrs Ma. Liza Cruz"         →  given="Ma."
  "Wm. H. Smith III"          →  given="Wm."
  "Chas. Smith, Ed"           →  suffix="Ed"
  "John Smith Ma."            →  family="Ma."
  "Smith, John Ma"            →  middle="Ma"
  ```
- **A connective after the abbreviation** (P3): the join takes it with the word after the connective before the shape is asked of it, so the two read as two names joined.
  ```
  "Xyz. and Mary Smith"       →  given="Xyz. and Mary"
  ```

**Accepted:**

- The shape is only recognizable as an unbroken run of letters, so an abbreviation in a script whose letters carry combining vowel signs (Bengali, Devanagari) never reads as a title by shape — an unlisted abugida honorific stays a name word, and only vocabulary can recognize it — which is what #343 and #344 supply for Bengali and Devanagari.
  ```
  "প্রকৌশলী. Sen"             →  given="প্রকৌশলী."
  ```
- The shape reads a Latin convention, and a script with no initials has no period abbreviations either, so a period-marked opening word carrying a Han, kana or hangul character — as the script table classifies them, halfwidth katakana included since #594 — is a name word and never a title by shape (#323; decisions/cjk-full-stops) — the same veto that keeps 씨. from reading as an initial. The Latin reading is unchanged, and W3's example block carries the CJK reading this clause vetoes into. The veto reads the composed spelling, so hangul typed decomposed, as conjoining jamo the script table does not hold, is hangul to it too (#665); the second line below is typed that way.
  ```
  "Smith. John"               →  title="Smith."
  "김. 민준"                    →  title=""
  ```
- Before a family comma the shape does not fire: the titles there are the vocabulary's alone (H6), so an unlisted abbreviation opening that part stays in the family.
  ```
  "Xyz. Smith, John"          →  family="Xyz. Smith"
  ```

---
**Signal:** shape: an unlisted word of two or more letters ending in its one period, opening the given-name part, which a given name written short declines
**history:** decisions/H2 · **implemented:** nameparser/_pipeline/_assign.py, nameparser/_pipeline/_classify.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
