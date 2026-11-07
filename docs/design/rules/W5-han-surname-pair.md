# W5 — a Han surname pair

**When:** Han division is active (W1), every word of the name is Han and the name is read family-first (W4), and the name opens with a Han name of four characters whose first two are each a listed single surname, written undivided or with a space after the pair alone, as in "王李小明".

**Then:** the two surnames are the family, in two units, and the last two characters are the given name.

- **The units are the surname views' units**: the first surname is the first-surname view (R11) and the second the second-surname view (R10), as two-family-name handling marks its own.
  ```
  "王李小明"  [zh]  →  surname1="王"
  "王李小明"  [zh]  →  surname2="李"
  ```
- **The space after the pair is read as the end of the family**, where the word after it has the two characters of a given name.
  ```
  "王李 小明"  [zh]  →  family="王李"
  "王李 小明"  [zh]  →  given="小明"
  ```

**Because:** a married woman in Taiwan wrote her husband's surname before her own (冠夫姓), the Civil Code's default until its 1998 amendment made it a choice, and a mainland child may carry both parents' surnames the same way. A Han given name is nearly always one or two characters, so a four-character name opening with two surnames is that pair far more often than one surname before a three-character given name. Counting four characters keeps the rule off three-character names, nearly always one surname before a two-character given name, where a pair would cut the given name in half, which is why no married pair is listed as a compound.

```
"王李小明"  [zh]  →  family="王李"
"王李小明"  [zh]  →  given="小明"
"王李小明先生"  [zh]  →  family="王李"
"王李小明"    →  family="王李小明"  · boundary
"李林伟"  [zh]  →  family="李"  · boundary
"王李小明丽"  [zh]  →  family="王"  · boundary
"王李"  [zh]  →  family="王"  · boundary
"王李 先生"  [zh]  →  family="王"  · boundary
"李林 伟"  [zh]  →  family="李"  · boundary
"王李, 小明"  [zh]  →  surname2=""  · boundary
"김이수진"    →  family="김"  · boundary
```

**Except:**

- **A listed compound keeps its reading**, its two characters one surname, though each is a listed single surname too.
  ```
  "歐陽小明"  [zh]  →  family="歐陽"
  "歐陽小明"  [zh]  →  surname2=""
  ```

**Precedence:**

- **Against W1's longest listed surname first** ("王李小明" and "王李 小明", where 王 is the longest listed surname opening the first word): this rule wins, and the name divides after both surnames, because the length says the given name ends the name in two characters; the parse reports the division it decided for the undivided writing, naming W1's reading as the other.
  ```
  "王李小明"  [zh]  →  given="小明"
  "王李 小明"  [zh]  →  given="小明"
  ```

**Accepted:**

- A real three-character given name whose first character is also a listed surname, behind a single surname, loses that character to the family, a transcribed one included, and the corpus the rule was measured on has no fields to count these.
  ```
  "王安琪拉"  [zh]  →  family="王安"
  ```
- A Japanese name of four kanji whose first two are each a listed Chinese surname divides after both, the right family for most such names, though the views then report one Japanese surname as two units.
  ```
  "高田栄二"  [zh]  →  family="高田"
  "高田栄二"  [zh]  →  surname2="田"
  ```
- A name holding a word in another script, a title written in Latin letters included, keeps W1's division even where it is read family-first, since the division is made before the order is known, and a division the order then read otherwise would move the name.
  ```
  "Dr. 王李小明"  [zh]  →  family="王"
  ```

---
**Signal:** script: an undivided Han word of four characters whose first two are each a listed single surname, in a name read family-first, the space after the pair counting as no division
**history:** decisions/W5 · **implemented:** nameparser/_pipeline/_script_segment.py, nameparser/_pipeline/_post_rules.py
