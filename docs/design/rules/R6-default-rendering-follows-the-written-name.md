# R6 — the default rendering follows the written name

**When:** a parsed name is rendered with no format of the caller's, by `str()` or by `render()` with no spec, as in "김민준" or "John Smith, Jr.".

**Then:** the name is laid out in the order it was read in, and two words that stand one directly after the other, in the same order, both as written and as laid out keep the separator written between them, normalized.

- **The layout follows the order.** A name read given-first, and every name with a family comma, is laid out title, given name, nickname in quotes, middle names, family name, maiden name in parentheses, suffix; a name read family-first keeps the title first and the suffix last, and puts the family name with its maiden name first among the name words, then the given and middle names in the order's own sequence, the nickname beside the given name.
  ```
  "Dr. Wang Xiaoming Jr."  family-first  →  str="Dr. Wang Xiaoming Jr."
  "Nguyen Van Anh"  family-first-given-last  →  str="Nguyen Van Anh"
  "Wang Xiaoming, Jr."  family-first  →  str="Wang Xiaoming, Jr."
  ```
- **The separator is normalized by its kind.** Nothing stays nothing; whitespace of any kind and length, the ideographic space included, becomes one space; an interpunct or a nakaguro the name is divided at stands alone, with no space around it; and one comma is written with no space before it and one after if ASCII or Arabic, and alone if full-width, a full-width comma carrying its own width.
  ```
  "王小明先生"                 →  str="王小明先生"
  "山田　太郎"                 →  str="山田 太郎"
  "ジョン ・ スミス"             →  str="ジョン・スミス"
  "John Smith ,Jr."         →  str="John Smith, Jr."
  "John Smith， Jr."         →  str="John Smith，Jr."
  ```
- **Every other pair takes the layout's own joiner**: a space, or the decoration standing between the two words' fields (the nickname's quotes, the maiden name's parentheses), and credentials not written side by side are joined with a comma as the suffix field joins them (R1). That covers a delimiter, a marker word, two commas, a hyphen, a slash, a zero-width or directional mark, and any two words the layout moves apart or turns round, a family comma's pair among them.
  ```
  "John (Jack) Smith"         →  str="John \u0022Jack\u0022 Smith"
  "Jane Smith née Jones, PhD"  →  str="Jane Smith (Jones) PhD"
  "Smith, John"  family-first  →  str="John Smith"
  "Smith, John, Jr."          →  str="John Smith Jr."
  ```

**Because:** a rendering should give back the name in the order the parse read it and with the separators its writer chose, its spacing normalized. A format a caller writes renders exactly as written, its order and its joiners, so a caller wanting another layout or the native spacing passes one, and the text as written stays in the parsed name's original.

```
"김민준"                      →  str="김민준"
"威廉·莎士比亚"                 →  str="威廉·莎士比亚"
"威廉 · 莎士比亚"               →  str="威廉 · 莎士比亚"
"John Smith, Jr."           →  str="John Smith, Jr."
"Smith, John"               →  str="John Smith"  · boundary
```

**Except:**

- **A family comma is never kept**, also where its pair stays side by side in the same order: when the part after it went to the family (P1's fold after a family comma), the comma stands between two family words and is dropped there too.
  ```
  "Smith, de Mesnil Jean"     →  str="Smith de Mesnil Jean"
  ```

**Accepted:**

- Two writings of one name can render differently, the rendering following each writing: "John Smith, Jr." keeps its comma where "Smith, John, Jr." has none to keep, its suffix laid out away from the given name it was written after.
- The title stays first under a family-first order, where most of CLDR's surname-first patterns put it after the family name: the title is placed only where the parse reads it back, and under a family-first order the parse reads a bare title only at the front (#938).
  ```
  "Senator Wang Xiaoming"  family-first  →  str="Senator Wang Xiaoming"
  ```
- A rendering need not read back as the name it came from. A family-comma name under a family-first order is laid out given-first, and the same parser reads the result family-first; a family comma in a name written in Han, Hangul or kana, a shape nobody writes (W3), reads back family-first by its script; a family comma dropped after P1's fold leaves a name read given-first; and a comma between two titles written after a comma, which the layout moves to the front, is kept, and reads back as a family comma, from whichever comma part the titles come.
  ```
  "김, 민준"                     →  str="민준 김"
  "John Smith, Jr., Dr., Prof."  →  str="Dr., Prof. John Smith, Jr."
  "John Smith Dr., Prof."     →  str="Dr., Prof. John Smith"
  ```
- Two equal names can render differently. The order a name was read in is not compared, so a name loaded from a 2.x pickle, which recorded none, renders given-first where a fresh parse of the same text renders family-first. (The shape needs a pickle written by an older release, so no example line.)

---
**Signal:** separator + none in the name: the order the name was read in
**history:** decisions/R6 · **implemented:** nameparser/_render.py, nameparser/_pipeline/_assemble.py
