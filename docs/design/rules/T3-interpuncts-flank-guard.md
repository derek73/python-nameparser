# T3 — the interpunct's flank guard

**When:** a name holds the interpunct U+00B7, as in "威廉·莎士比亚".

**Then:** the interpunct divides a name only between two characters of a classified East Asian script; anywhere else it is part of the word.

**Because:** U+00B7 is two marks in one codepoint — the Chinese 间隔号 dividing a transcribed foreign name, and the Catalan punt volat interior to words.

```
"威廉·莎士比亚"              →  family="莎士比亚"
"Gal·la Serra"              →  given="Gal·la"  · boundary
```

---
**Signal:** neighbor: the characters flanking an interpunct
**history:** decisions/T3 · **implemented:** nameparser/_pipeline/_tokenize.py
