# H2 — the leading-abbreviation title

**When:** a period-marked word opens the part of the name that carries the given name, as in "Rev. John Smith".

**Then:** an abbreviation opening the part of the name that carries the given name — the whole name, or the part after a family comma — reads as a title even when unlisted, provided it is an unbroken run of two or more letters ending in its one period, the shape outranking vocabulary where it fires, so that a period-marked opening word is a title even when the word is suffix vocabulary, save a credential opening the part after a family comma (C13) and a given name written short.

- **A single-letter initial does not** (T5), and neither does anything with interior periods, hyphens or digits.
  ```
  "J. Smith"                  →  given="J."  · boundary
  "J.R. Smith"                →  given="J.R."  · boundary
  "Ю. А. Чибрикова"           →  given="Ю."  · boundary
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

- **A word in one of the ten Brahmic scripts from Devanagari to Sinhala** — Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam and Sinhala — never reads as a title by shape, even where it is a run of letters: these scripts spell a Latin initial out by its sound, and where the spelling needs no vowel sign, as "एम." spells "M.", it is two letters and an initial, not an abbreviation (#1191). A listed title there keeps its reading, and these scripts still write initials. Thai and Lao, abugidas outside these, abbreviate titles with a period and no vowel sign, and the shape reads them, as it reads any script outside the ten, the Brahmic scripts India writes beyond them (Meetei Mayek, Limbu) included.
  ```
  "एम. एस. वर्मा"               →  given="एम."
  "এম. আবদুল লতিফ"             →  title=""
  "ਐਮ. ਸਿੰਘ"                    →  given="ਐਮ."
  "डा. राम वर्मा"               →  title="डा."  · boundary
  "ดร. สมชาย ใจดี"              →  title="ดร."  · boundary
  "ດຣ. ສົມ"                     →  title="ດຣ."  · boundary
  ```

- **A transliteration digraph** — the Latin spelling of one Cyrillic letter, Yu, Ya, Ye, Yo, Zh, Kh, Shch or Dzh, in any case — never reads as a title by shape: it is the initial of that letter, so a romanized byline reads as its Cyrillic original does, where the one-letter initial is no title either (#1136). Ch, Sh and Ts still read as titles by shape, each also written short for a title (Chaudhry, Sheikh or Shri, the Malaysian Ts.), and outside this clause are a digraph of another alphabet, such as Th for the Greek Θ, and a Latin given name written short, such as the Dutch Th. for Theodorus. The digraph reads as a name word wherever it stands, behind a title too, and not as the initial a single letter is, so a lone one is placed as any lone unlisted word is.
  ```
  "Yu. A. Chibrikova"         →  given="Yu."
  "Chibrikova, Yu. A."        →  given="Yu."
  "Dr. Yu. Petrov"            →  title="Dr."
  "Vice Yu. Petrov"           →  given="Vice"
  "ZH. I. ALFEROV"            →  given="ZH."
  "Kh. O. Bezirdzhyan"        →  given="Kh."
  "Yu. Smith, Ed"             →  suffix="Ed"
  "Ts. Dr. Norziha Che Him"   →  title="Ts. Dr."  · boundary
  "Ch. Tahir Mehmood"         →  title="Ch."  · boundary
  ```

**Precedence:**

- **A credential opening the part after a family comma** ("Smith, Esq. John"): C13 wins, and the part is postnominal: a suffix word that starts S8's run makes the part its postnominals however it goes on. The shape still reads as a title there an abbreviation that starts no such run — an unlisted one, or a listed suffix word C13 does not open with, such as a word of the ambiguous class.
  ```
  "Smith, Esq. John"          →  suffix="Esq. John"
  "Smith, Insp. John"         →  title="Insp."
  "Smith, Do. John"           →  title="Do."
  ```
- **A given name written short** ("Chas. Smith", "Ma. Cristina Reyes"): an abbreviation the vocabulary reads as a given name written short is that given name, outranking the shape — traditional English abbreviations such as Chas. and Wm., the Filipino Ma. (María) and Jo. (José), and Muhammad written short (Mohd., Muh.) — so the name reads as it would with the full given name in that place, behind a title too ("Mrs Ma. Liza Cruz"), and C4's count of the name words before a comma, which asks this shape, counts it as one; its period still keeps it out of the case contrast C6 reads, as an initial's does ("Chas. SMITH, XYZ" reads as "J. SMITH, XYZ"). Only the shape yields: a word listed as a title is still one, and written bare, or anywhere but the head of the part that carries the given name, the word reads as it would unlisted, so "Ma" keeps its surname and credential readings.
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

- The shape is only recognizable as an unbroken run of letters, so an abbreviation whose letters carry combining vowel signs never reads as a title by shape — an unlisted abugida honorific stays a name word, and only vocabulary can recognize it — which is what #343 and #344 supply for Bengali and Devanagari.
  ```
  "প্রকৌশলী. Sen"             →  given="প্রকৌশলী."
  "คุณ. สมชาย"                 →  given="คุณ."
  ```
- The shape reads a Latin convention, and a script with no initials has no period abbreviations either, so a period-marked opening word carrying a Han, kana or hangul character — as the script table classifies them, halfwidth katakana included since #594 — is a name word and never a title by shape (#323; decisions/cjk-full-stops) — the same veto that keeps 씨. from reading as an initial. The Latin reading is unchanged, and W3's example block carries the CJK reading this clause vetoes into. The veto reads the composed spelling, so hangul typed decomposed, as conjoining jamo, is hangul to it too (#665); the second line below is typed that way.
  ```
  "Smith. John"               →  title="Smith."
  "김. 민준"                    →  title=""
  ```
- Before a family comma the shape does not fire: the titles there are the vocabulary's alone (H6), so an unlisted abbreviation opening that part stays in the family.
  ```
  "Xyz. Smith, John"          →  family="Xyz. Smith"
  ```

---
**Signal:** shape + script: an unlisted word of two or more letters ending in its one period, opening the given-name part, which a given name written short or a transliteration digraph declines, and which a word in a CJK or Brahmic script never is
**history:** decisions/H2 · **implemented:** nameparser/_pipeline/_assemble.py, nameparser/_pipeline/_assign.py, nameparser/_pipeline/_classify.py, nameparser/_pipeline/_pieces.py, nameparser/_pipeline/_vocab.py
