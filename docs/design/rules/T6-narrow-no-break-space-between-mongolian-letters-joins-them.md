# T6 — a narrow no-break space between Mongolian letters joins them

**When:** a name in Mongolian script holds the narrow no-break space U+202F between two of its letters, a letter here being any character of the script but its punctuation and digits, its variation selectors and vowel separator included, as in "ᠬᠣᠷᠯᠤ᠎ᠠ ᠶ᠋ᠢᠨ ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ".

**Then:** a narrow no-break space between two Mongolian letters joins them into one word; anywhere else it divides the name like any other whitespace.

**Because:** Mongolian script writes a case suffix apart from its stem and joins the two with U+202F, so between its letters the character is the suffix connector, not a space between words.

```
"ᠬᠣᠷᠯᠤ᠎ᠠ ᠶ᠋ᠢᠨ ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ"  family-first  →  family="ᠬᠣᠷᠯᠤ᠎ᠠ ᠶ᠋ᠢᠨ"
"Jean Dupont"               →  given="Jean"  · boundary
```

**Accepted:**

- A word joined this way cannot be listed in the vocabulary, which reads U+202F as a space between two words, so a caller's entry for it is refused as a phrase.
- A case suffix written after an ordinary space is a word of its own, since only the connector marks it.
  ```
  "ᠬᠣᠷᠯᠤ᠎ᠠ ᠶ᠋ᠢᠨ ᠴᠣᠢᠢᠪᠠᠯᠰᠠᠩ"  family-first  →  given="ᠶ᠋ᠢᠨ"
  ```

---
**Signal:** neighbor: the characters on each side of a narrow no-break space
**history:** decisions/T6 · **implemented:** nameparser/_pipeline/_tokenize.py, nameparser/_render.py
