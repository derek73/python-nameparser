# T2 — a script's own word divider divides like a space

**When:** a name holds the katakana middle dot, its halfwidth twin or the Ethiopic wordspace, as in "マイケル・ジャクソン".

**Then:** the katakana middle dot, its halfwidth twin and the Ethiopic wordspace divide a name like whitespace, always.

**Because:** each is a character of one script that exists to divide words, and none appears inside a word of any name.

```
"マイケル・ジャクソン"        →  given="マイケル"
"高橋・一郎"                 →  family="高橋"
"አበበ፡ከበደ፡ተሰማ"            →  middle="ከበደ"
```

---
no-boundary: the separation is unconditional; the context-sensitive interpunct is T3's subject.
**Signal:** character: the katakana middle dot, its halfwidth twin or the Ethiopic wordspace
**history:** decisions/T2 · **implemented:** nameparser/_pipeline/_tokenize.py
