# P12 — a bound given name and the word that completes it

**When:** a bound given-name word stands past the first name word, and the word after it is one the vocabulary lists as completing it, as in "طارق عبد العزيز", or a plain name word after a bound word whose reading completes with any name; or a word the vocabulary lists as written second in a pair stands after a plain name word anywhere in the name, as in "سامر عز الدين".

**Then:** the two words are one name unit, past the first name word or, for a pair read from its second word, at it too, a unit that position places.

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
- **A listed second word completes the plain word before it** (a `bound_second` reading): Arabic script writes many given names as a varying word and `الدين` (of the faith) or `الله` after it, the Persian spellings `الدین` and `اله` and the Urdu `اللہ` too, and the word before varies past any list, several of those words being given names alone, so the license is the second word, and it is read from wherever the pair stands; a reading written `completes` joins behind the words it lists alone (`ذو` before `الغنى` and `الفقار`).
  ```
  "نور الدين سامر حداد"       →  given="نور الدين"
  "سامر عز الدين"             →  family="عز الدين"
  "ليلى شكر الله"             →  family="شكر الله"
  "سامر ذو الغنى"             →  family="ذو الغنى"
  "سامر نور الدين حداد"       →  middle="نور الدين"
  "نصر اله رضایی"             →  given="نصر اله"
  "سامر بن الله"              →  family="بن الله"  · boundary
  ```

**Because:** Arabic script writes a theophoric given name as two words, `عبد` (servant of) and the name of God it serves, `عبد الله`, so a name holding two of them, or one behind a given name, puts the second word where a family name would stand alone. In Arabic script the words that complete `عبد` are a closed set, the names of God and a few devotional names, so the vocabulary can list them, and a list is certain where a shape is not (the article `ال` opens a nisba surname as readily as a name of God), while a Latin spelling drops the article and names no word, leaving a name word's place as the only signal. Researchers who split such a name into boxes put the pair in the family box together.

**Except:**

- **A bound word at the first name word is P5's**, which joins it to the word after it with its reserve, so a bound word with no word to spare there keeps its two words apart; a pair read from its second word joins there instead, its first word being no bound word for P5 to read.
  ```
  "عبد الله"                  →  given="عبد"
  ```
- **A pair read from its second word needs a third name word**: where the pair holds every name word the name is read as having, its two words are two names, as P5's reserve keeps a bound word's, save after a family comma and behind a given-name title, where P5 joins too.
  ```
  "عز الدين"                  →  given="عز"
  "Dr. عز الدين"              →  given="عز"
  "عز الدين Jr."              →  given="عز"
  "عز الدين PhD الحاج"        →  given="عز"
  "عز الدين الحاج"            →  given="عز الدين"
  "عز الدين الابن حداد"       →  given="عز الدين"
  "الدكتور عز الدين"          →  given="عز الدين"
  "، عز الدين"                →  given="عز الدين"
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

**Precedence:**

- **P5's join of a bound word opening the name** takes the plain word after it before a pair read from that word's second word can: the bound word's join is P5's, and the pair is split.
  ```
  "أبو نور الدين سامر"        →  given="أبو نور"
  ```

**Accepted:**

- A completing word written with its vowel points or with the alef wasla (`ٱلله`, `اَلله`) is not listed, and keeps its words apart; one JRC-Names spelling held one after `عبد` on 2026-11-04 (`عبد ِالعزيز`).
- A connective's join takes the word after it first (P3), so a pair behind a connective stays apart: `طارق عبد الله و عبد الرحمن` reads middle 'عبد الله و عبد', family 'الرحمن'.
- A writer who counts `Abdul` a middle name of its own in a name of four words reads the pair joined all the same: `Nadia Ali Abdul Rahim` gives family 'Abdul Rahim' where such a writer would have the family 'Rahim'.
- A word read as a title that no title reading lists is a name word, and a listed second word joins it: `آية الله سامر حداد` gives given 'آية الله', the title Ayatollah.
- A kunya opening the name is P5's join of its two bound words, and the word completing the second is left to position (`أبو عبد الله محمد` reads given 'أبو عبد', middle 'الله'), as before this rule; behind a given name the kunya is the family (`محمد أبو عبد الله`).

---
**Signal:** neighbor: a bound given-name word and the word after it, which its reading lists, or which carries no vocabulary after one that completes any, `abdul` only in a name of four name words or more + neighbor: a word listed as written second and the plain word before it
**history:** decisions/P12 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_group.py, nameparser/_pipeline/_post_rules.py
