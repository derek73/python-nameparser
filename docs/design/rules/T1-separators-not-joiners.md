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

**Accepted:**

- A zero-width joiner or non-joiner stays inside the word even at its edge, where it joins nothing, since between letters it decides how they join.
  ```
  "Antonio ‌Negri"  →  family="‌Negri"
  ```
- A zero-width space or byte-order mark does not count as a space where a quote or a maiden marker is recognized, as the katakana middle dot does not (rules/T2): a marker glued to its name by one leaves the clause a nickname.
  ```
  "Jane (née​Jones) Smith"  →  nickname="née Jones"
  ```
- A zero-width space after a hyphen, a line-break hint in typeset text, divides the hyphenated name.
  ```
  "Mary-​Jane Smith"  →  given="Mary-"
  ```

---
**Signal:** character: whitespace, and characters that carry no name content
**history:** decisions/T1 · **implemented:** nameparser/_pipeline/_tokenize.py
