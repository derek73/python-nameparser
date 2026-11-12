# W4 — script-scoped order

**When:** a name is written wholly in one East Asian script, or in the kana-licensed Japanese repertoire, as in "山田 太郎".

**Then:** a name written wholly in one East Asian script, or in the kana-licensed Japanese repertoire, reads family-first whatever order the caller declared; a wholly-katakana name keeps the declared order.

- **A name the katakana middle dot divides still reads by the script license**: that divider (T2) carries no transcription signal.
  ```
  "威廉・莎士比亚"            →  family="威廉"
  ```

**Because:** Chinese, Japanese and Korean all write the family name first in native script — the script settles the order without knowing the language — while a wholly-katakana name may be a transcribed foreign name already in its source order or a Japanese reading written family-first, so its script settles nothing.

```
"김 민준"                   →  family="김"
"山田 太郎"                 →  family="山田"
"高橋 みなみ"               →  family="高橋"
"山田 ﾀﾛｳ"                  →  family="山田"
"マイケル ジャクソン"        →  given="マイケル"  · boundary
"ﾔﾏﾀﾞ ﾀﾛｳ"                  →  given="ﾔﾏﾀﾞ"  · boundary
"ア゙イ タロウ"                 →  given="ア\u3099イ"  · boundary
```

**Except:**

- **A name the interpunct divides** keeps the declared order — the divider itself marks a transcription (T3) — so the override stands down there, and the name reads as a wholly-katakana one does: in its written order by default, reversed by a declared family-first order like any other name.
  ```
  "毛·泽东"                   →  given="毛"
  "威廉·莎士比亚"  family-first  →  family="威廉"
  ```
- **A pack's order for a script that settles no order** reads a name written wholly in that script, licensed by the caller's choice of the pack rather than by the script: Cyrillic is written in both orders, so the default reads it by the declared order, and only `locales.MN`, whose Mongolian names write the father's name first, gives it an entry; a lone word in it stays O5's convention, the entry settling no field.
  ```
  "Батын Сүхээ"  [mn]          →  family="Батын"
  "Batyn Sükhee"  [mn]         →  given="Batyn"  · boundary
  "Батын Сүхээ"                →  given="Батын"  · boundary
  "Сүхээ"  [mn]                →  given="Сүхээ"
  ```

---
**Signal:** script: a name written wholly in one East Asian script, or in the kana-licensed repertoire, or in a script a chosen pack gives an order
**history:** decisions/W4 · **implemented:** nameparser/_pipeline/_assign.py
