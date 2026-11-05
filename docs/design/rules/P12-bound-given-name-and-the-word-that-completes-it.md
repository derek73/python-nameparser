# P12 — a bound given name and the word that completes it

**When:** a bound given-name word stands past the first name word, and the word after it is one the vocabulary lists as completing it, as in "طارق عبد العزيز".

**Then:** the two words are one given name wherever they stand, a name unit that position places.

- **The completing word is one a reading lists** (`completed_by` on the bound word's reading): for Arabic-script `عبد`, the one-word names of God, the other divine epithets and the devotional completions written after it, each in its hamza-less and Persian spellings.
  ```
  "سعيد عبد الله"             →  family="عبد الله"
  "طارق عبد العزيز"           →  family="عبد العزيز"
  "محمد عبد الله أحمد"        →  middle="عبد الله"
  "عبد اللطيف عبد الحميد"     →  family="عبد الحميد"
  "علي عبد الکریم"            →  family="عبد الکریم"
  ```
- **A word the list leaves out completes nothing**, though it opens with the article: after the bound word stands a short given name of its own, or a nisba surname.
  ```
  "نوال عبد هاشم"             →  family="هاشم"  · boundary
  "محمد عبد القريشي"          →  family="القريشي"  · boundary
  ```

**Because:** Arabic script writes a theophoric given name as two words, `عبد` (servant of) and the name of God it serves, `عبد الله`, so a name holding two of them, or one behind a given name, puts the second word where a family name would stand alone. Which words complete `عبد` is a closed set, the names of God and a few devotional names, so the vocabulary can list them, and a list is certain where a shape is not: the article `ال` opens a nisba surname as readily as a name of God. Researchers who split such a name into boxes put the pair in the family box together.

**Except:**

- **The first name word is P5's**, which joins a bound word there to the word after it with its reserve, so a bound word with no word to spare there keeps its two words apart.
  ```
  "عبد الله"                  →  given="عبد"
  ```
- **A bound word listing nothing joins only at the start**: the Latin spellings `abdul`, `abdel` and `abdal` list no word, the pair standing behind a given name as a middle name about as often as a family.
  ```
  "Tariq Abdul Aziz"          →  middle="Abdul"
  ```

**Accepted:**

- A completing word written with its vowel points or with the alef wasla (`ٱلله`, `اَلله`) is not listed, and keeps its words apart; no corpus held one after `عبد` on 2026-11-04.
- A completing word with punctuation glued to it (`عبد الله،`) is not listed either: the Arabic comma is no comma to the parser.

---
**Signal:** neighbor: a bound given-name word and the word after it, which its reading lists
**history:** decisions/P12 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py
