# W3 — the writer's divisions are respected

**When:** a name in an East Asian script is written in a listing form: with a comma, as in "남궁민수, 지훈", or with the punctuation such a listing carries in with it, such as an edge full stop.

**Tolerated:** none of the East Asian writing systems declares a family name with a comma (the W section's Background), and native CJK writing puts no edge full stop of any width on a name word, so every input this rule reads is a listing convention wrapped around a name whose own script has already arranged it. What follows describes what the parser does with such input; it does not promise it: the examples carrying a comma or a period illustrate current behavior, changeable without notice, while "남궁민수", carrying neither, is W1's claim, which is normative.

**Then:** under a family comma the pre-comma text is the family by declaration and never divides, and the post-comma side is given text with no family to find.

- **Which side of the comma the honorific split-off (W2) takes from** is decided by the SHAPE of the part after the comma, not by which of C1's two readings that part selects — a one-word family reads the listing form either way. A part that is nothing but suffix words is not the name's end: it is declined as the site, and the split-off falls back to the part before the comma and takes the honorific there, provided that part offers a site of its own. Any other part — a title, a name word — IS the name's end, and a glued honorific before the comma stays glued.
  ```
  "田中さん, Dr."             →  family="田中さん"
  "田中さん, PhD"             →  suffix="さん, PhD"
  ```
- **The vocabulary question is C1's own**, asked without C1's word-count condition: the two differ in what else they require, not in what they ask of the words — the written-case evidence S6 reads included, so a post-comma acronym the case leans credential declines the side it stands on here exactly as it reads as the credential there, and the honorific comes off the part before the comma as it does behind a settled credential.
- **A period the listing leaves behind** is not what licenses the step past a post-nominal word, and it is not ignored either. The step is W2's, taken on the vocabulary alone and taken with no punctuation anywhere in the input; a period on a SEPARATE post-nominal word rides along into the suffix and moves no division (田中さん 様. divides where 田中さん 様 does).
  ```
  "田中さん 様."              →  suffix="さん 様."
  ```
- **A period glued to the honorific's OWN word rides with the honorific**: the split-off matches the listed tail through it and cuts before it, so 田中さん. and 김민준씨. divide where 田中さん and 김민준씨 do.
  ```
  "김민준씨."                 →  suffix="씨."
  ```
- **A period-marked Han opener divides as its stop-less spelling does**, 田中. 太郎 reading family-first — the reading H2's Accepted clause vetoes a title into, carried here because an edge full stop makes it tolerated input like the rest of this rule.
  ```
  "田中. 太郎"                →  family="田中."
  ```

**Because:** a family name declared by a comma is the writer's own division, and re-dividing it would invent a boundary nobody drew.

```
"남궁민수"                  →  family="남궁"
"지훈, 남궁민수"            →  given="남궁민수"
"남궁민수, 지훈"            →  family="남궁민수"  · boundary
```

**Except:**

- **Behind a part C1 reads as postnominal there is no family comma**, and the name before it divides as it would with no comma ('마틴 킹, MA' as '마틴 킹'). The division, and with it the honorific split-off, follows C1's own reading of the comma, taken on the name as written before the division ('Dr 김민준, MA' divides as 'Dr 김민준' does).
  ```
  "Kim김민준씨, MA"           →  suffix="씨, MA"
  ```

**Precedence:**

- **A title run opening the pre-comma text** ("Dr. 김민준, 지훈"): the title run is H6's title, not family text.
- **The honorific split-off against the comma** ("田中さん, PhD"): only the honorific split-off (W2) crosses the comma, an honorific being no part of the name on either side.

---
**Signal:** comma + edge full stop
**history:** decisions/W3 · **implemented:** nameparser/_pipeline/_script_segment.py
