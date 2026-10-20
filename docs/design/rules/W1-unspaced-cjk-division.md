# W1 — unspaced CJK division

**When:** an undivided word stands in the family position of a name written in a script whose division is active, as in "남궁민수".

**Then:** an undivided word in the family position of a name written in an activated script divides after a recognized surname, the longest recognized surname first; where the vocabulary recognizes nothing, an optional segmenter may divide instead, and with neither the word stays whole rather than divide in a wrong place.

- **Korean division is active by default; Han division is opt-in.**
- **A segmenter** — unlike the vocabulary, which ignores spacing but not the interpunct (the Except below) — is consulted only for a name whose written form is wholly undivided, a spaced honorific counting as a written division (decisions/W3 records what that trade keeps and costs).

**Because:** hangul is monoglot Korean and its surnames are a closed census set, so an unspaced hangul name divides at a certain point; Han carries no such certainty by default.

```
"김민준"                    →  family="김"
"남궁민수"                  →  family="남궁"
"남궁민수 지훈"             →  family="남궁"
"毛泽东"                    →  family="毛泽东"  · boundary
"毛泽东"  [zh]              →  family="毛"
"高橋一郎"  [zh]            →  family="高"
"柯洁"  [zh]                →  family="柯"
"钟离小凤"  [zh]            →  family="钟离"
"张简"  [zh]                →  family="张简"
```

**Except:**

- **A name the interpunct divides** is already divided in the sense that matters — division stands down entirely there, vocabulary and segmenter alike (#298; decisions/T3).
  ```
  "安东尼·陈志明"  [zh]        →  family="陈志明"
  ```

---
**Signal:** script: an undivided word in the family position, in a script division is active for
**history:** decisions/W1 · **implemented:** nameparser/_pipeline/_script_segment.py
