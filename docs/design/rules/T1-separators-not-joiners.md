# T1 — separators, not joiners

**When:** a name holds whitespace or an ignorable character, one that carries no name content, such as an emoji, an invisible directionality control, a zero-width space or a byte-order mark, as in "John😀Smith".

**Then:** the name splits at each of them, so an ignorable character separates its neighbors and never joins them.

**Because:** a character that carries no name content stands between words, not inside them.

```
"John😀Smith"                →  family="Smith"
"​王小明"                    →  family="王小明"
"​Dr. John Smith"          →  title="Dr."
```

**Except:**

- **Where the caller opts to keep emoji or directionality controls**, the name does not split at the ones kept; a zero-width space and a byte-order mark have no such opt-out.
  ```
  "John😀Smith"  keep-emoji    →  given="John😀Smith"  · boundary
  ```

---
**Signal:** character: whitespace, and characters that carry no name content
**history:** decisions/T1 · **implemented:** nameparser/_pipeline/_tokenize.py
