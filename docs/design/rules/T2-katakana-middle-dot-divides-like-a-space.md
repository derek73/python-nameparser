# T2 — the katakana middle dot divides like a space

**When:** a name holds the katakana middle dot or its halfwidth twin, as in "マイケル・ジャクソン".

**Then:** the katakana middle dot and its halfwidth twin divide a name like whitespace, always.

**Because:** the katakana middle dot exists to divide name parts and appears in no native name.

```
"マイケル・ジャクソン"        →  given="マイケル"
"高橋・一郎"                 →  family="高橋"
```

---
no-boundary: the separation is unconditional; the context-sensitive interpunct is T3's subject.
**Signal:** character: the katakana middle dot or its halfwidth twin
**implemented:** nameparser/_pipeline/_tokenize.py
