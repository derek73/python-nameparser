# W5 — a Han surname pair

**When:** Han division is active (W1) and a Han name of four characters whose first two are each a listed single surname is written undivided, as in "王李小明".

**Then:** the two surnames are the family, in two units, and the last two characters are the given name.

- **The units are the surname views' units**: the first surname is the first-surname view (R11) and the second the second-surname view (R10), as two-family-name handling marks its own.
  ```
  "王李小明"  [zh]  →  surname1="王"
  "王李小明"  [zh]  →  surname2="李"
  ```
- **A pair the writer ended with a space is read the same way**: a word of two listed single surnames with a Han name written after it divides into its two units, and the name after it is the given name.
  ```
  "王李 小明"  [zh]  →  family="王李"
  "王李 小明"  [zh]  →  given="小明"
  "王李 小明 美华"  [zh]  →  middle="美华"
  ```

**Because:** a married woman in Taiwan wrote her husband's surname before her own (冠夫姓), the Civil Code's default until its 1998 amendment made it a choice, and a mainland child may carry both parents' surnames the same way. A Han given name is one or two characters, so a four-character name opening with two surnames is that pair far more often than one surname before a three-character given name. The length keeps the rule off three-character names, where a pair would cut a single surname's two-character given name in half, which is why no married pair is listed as a compound.

```
"王李小明"  [zh]  →  family="王李"
"王李小明"  [zh]  →  given="小明"
"王李小明"    →  family="王李小明"  · boundary
"李林伟"  [zh]  →  family="李"  · boundary
"王李小明丽"  [zh]  →  family="王"  · boundary
"王李"  [zh]  →  family="王"  · boundary
"王李 先生"  [zh]  →  family="王"  · boundary
"김이수진"    →  family="김"  · boundary
```

**Except:**

- **A listed compound keeps its reading**, its two characters one surname, though each is a listed single surname too.
  ```
  "歐陽小明"  [zh]  →  family="歐陽"
  "歐陽小明"  [zh]  →  surname2=""
  ```

**Precedence:**

- **Against W1's longest listed surname first** ("王李小明", where 王 is the longest listed surname opening it): this rule wins, and the name divides after both surnames, because the length says the given name ends the name in two characters; the parse reports the division it decided, naming W1's reading as the other.
  ```
  "王李小明"  [zh]  →  given="小明"
  ```

**Accepted:**

- A real three-character given name opening with a character that is also a listed surname, behind a single surname, loses that character to the family, and so does a transcribed foreign given name of three characters: the corpus the rule was measured on has no fields to count these.
  ```
  "王安琪拉"  [zh]  →  family="王安"
  ```
- A Japanese name of four kanji whose first two are each a listed Chinese surname divides after both, which is the reading of most such names, a two-kanji family before a two-kanji given name.
  ```
  "高田栄二"  [zh]  →  family="高田"
  ```

---
**Signal:** script: an undivided Han word of four characters whose first two are each a listed single surname, or of two with a Han name written after it
**history:** decisions/W5 · **implemented:** nameparser/_pipeline/_script_segment.py, nameparser/_pipeline/_post_rules.py
