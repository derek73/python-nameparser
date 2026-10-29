# R7 — no initials in a script that writes none

**When:** initials are asked of a parsed name holding a word written in Han, Hangul or kana, as in "김민준".

**Then:** a word whose first letter is in a script that writes no initials contributes nothing to the initials, and a word in another script beside it still gives its own.

**Because:** Han, Hangul and kana abbreviate no name to a letter, so the first character with a full stop after it is no initial anyone writes. The parse already reads no word in them as an initial, and no period after one as an abbreviation (H2), so the parse and this view answer that question alike.

```
"김민준"                      →  initials=""
"マイケル ジャクソン"            →  initials=""
"王 小明"                     →  initials=""
"김민준 John"                 →  initials="J."  · boundary
```

**Accepted:**

- A name written wholly in those scripts has empty initials, where 2.1 through 2.8 gave its first characters (`김민준` gave '민. 김.'); a caller wanting a character per word takes it from the fields.

---
**Signal:** script
**history:** decisions/R7 · **implemented:** nameparser/_render.py
