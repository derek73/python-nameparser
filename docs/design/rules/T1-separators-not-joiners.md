# T1 — separators, not joiners

**When:** a name holds whitespace or an ignorable character, one that carries no name content, such as an emoji or an invisible directionality control, as in "John😀Smith".

**Then:** the name splits at each of them, so an ignorable character separates its neighbors and never joins them.

**Because:** a character that carries no name content stands between words, not inside them.

```
"John😀Smith"                →  family="Smith"
```

**Except:**

- **Where the caller opts to keep ignorable characters**, the name does not split at the ones kept.
  ```
  "John😀Smith"  keep-emoji    →  given="John😀Smith"  · boundary
  ```

---
**Signal:** character: whitespace, and characters that carry no name content
**history:** decisions/T1 · **implemented:** nameparser/_pipeline/_tokenize.py
