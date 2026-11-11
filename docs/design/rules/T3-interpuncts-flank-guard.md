# T3 — the interpunct's flank guard

**When:** a name holds the interpunct U+00B7, as in "威廉·莎士比亚", or the fullwidth full stop U+FF0E written in its place, as in "台邦．撒沙勒".

**Then:** the interpunct divides a name only between two characters of a classified East Asian script; anywhere else it is part of the word.

- **Hangul typed decomposed is classified too:** a syllable written as its conjoining jamo flanks the interpunct as the composed syllable does; the line below is typed that way.
  ```
  "이서연·김민준"                   →  family="김민준"
  ```

- **The fullwidth full stop is guarded the same way:** Taiwan writes an Indigenous name's dot as U+FF0E, so between two classified characters it divides and marks a transcription as U+00B7 does; with a Latin neighbor it is a full stop like any other. The ideographic full stop U+3002 is the sentence stop and divides nothing.
  ```
  "台邦．撒沙勒"                   →  family="撒沙勒"
  "Kilang．Ｍanah"                →  given="Kilang．Ｍanah"
  "台邦。撒沙勒"                   →  given="台邦。撒沙勒"
  ```

**Because:** U+00B7 is two marks in one codepoint — the Chinese 间隔号 dividing a transcribed foreign name, and the Catalan punt volat interior to words; U+FF0E is the same dot typed with the fullwidth stop and, outside a classified script, a plain full stop.

```
"威廉·莎士比亚"              →  family="莎士比亚"
"Gal·la Serra"              →  given="Gal·la"  · boundary
```

---
**Signal:** neighbor: the characters flanking an interpunct
**history:** decisions/T3 · **implemented:** nameparser/_pipeline/_tokenize.py
