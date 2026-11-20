# P12 — a bound given name and the word that completes it

**When:** a bound given-name word stands past the first name word, and the word after it is one the vocabulary lists as completing it, as in "طارق عبد العزيز", or a plain name word after a bound word whose reading completes with any name.

**Then:** the two words are one name unit past the first name word, a unit that position places.

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
- **A Latin spelling completes with any plain name word** (`completes_any` on the bound word's reading): `abdul`, `abd`, `abdel`, `abdal` and `abou` write the bound word without the name it serves, so no list can say which word follows it, and a word the vocabulary reads otherwise, a particle among them, or an initial completes nothing.
  ```
  "Tariq Abdel Aziz"          →  family="Abdel Aziz"
  "Nadia Ali Abdul Rahim"     →  family="Abdul Rahim"
  "Nadia Abdul Rahim Ali"     →  middle="Abdul Rahim"
  "Ahmad Abdel bin Omar"      →  middle="Abdel"  · boundary
  "Ahmad Abdel K."            →  middle="Abdel"  · boundary
  ```

**Because:** Arabic script writes a theophoric given name as two words, `عبد` (servant of) and the name of God it serves, `عبد الله`, so a name holding two of them, or one behind a given name, puts the second word where a family name would stand alone. In Arabic script the words that complete `عبد` are a closed set, the names of God and a few devotional names, so the vocabulary can list them, and a list is certain where a shape is not (the article `ال` opens a nisba surname as readily as a name of God), while a Latin spelling drops the article and names no word, leaving a name word's place as the only signal. Researchers who split such a name into boxes put the pair in the family box together.

**Except:**

- **The first name word is P5's**, which joins a bound word there to the word after it with its reserve, so a bound word with no word to spare there keeps its two words apart.
  ```
  "عبد الله"                  →  given="عبد"
  ```
- **A bound word with neither joins only at the start**: a word whose reading neither lists a completion nor completes with any name is P5's alone.
  ```
  "Tariq Umm Aziz"            →  middle="Umm"
  ```
- **`abdul` in a name of three words stays apart** (`long_names_only` on its reading): the writers of `X Abdul Y` split it both ways by population, the pair the family in Malaysia and a middle name of its own in Bangladesh and in Britain, and the pair is joined only in a name of four name words or more, a title run at the head of a part counting as none, and after the pair only a plain name word, a bound given name or a pair of initials up to the next comma, a numeral written other than in Title case being no name word.
  ```
  "Tariq Abdul Aziz"          →  middle="Abdul"
  "Mr Tariq Abdul Aziz"       →  middle="Abdul"
  "Tariq Abdul Aziz Jr."      →  middle="Abdul"
  "The Rt Hon Nadia Abdul Rahim"  →  middle="Abdul"
  "Nadia Abdul Rahim, MA"     →  middle="Abdul"
  ```

**Accepted:**

- A completing word written with its vowel points or with the alef wasla (`ٱلله`, `اَلله`) is not listed, and keeps its words apart; one JRC-Names spelling held one after `عبد` on 2026-11-04 (`عبد ِالعزيز`).
- A connective's join takes the word after it first (P3), so a pair behind a connective stays apart: `طارق عبد الله و عبد الرحمن` reads middle 'عبد الله و عبد', family 'الرحمن'.
- A writer who counts `Abdul` a middle name of its own in a name of four words reads the pair joined all the same: `Nadia Ali Abdul Rahim` gives family 'Abdul Rahim' where such a writer would have the family 'Rahim'.
- A kunya opening the name is P5's join of its two bound words, and the word completing the second is left to position (`أبو عبد الله محمد` reads given 'أبو عبد', middle 'الله'), as before this rule; behind a given name the kunya is the family (`محمد أبو عبد الله`).

---
**Signal:** neighbor: a bound given-name word and the word after it, which its reading lists, or which carries no vocabulary after one that completes any, `abdul` only in a name of four name words or more
**history:** decisions/P12 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py
