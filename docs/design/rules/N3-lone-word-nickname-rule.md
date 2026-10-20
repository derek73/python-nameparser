# N3 — the lone-word nickname rule

**When:** a name is written as a nickname beside its name words, as in "'Smitty' Jones".

**Then:** a name that is only a nickname and one name word reads that word as the family name.

- **With two or more name words the ordinary positional reading applies.**
  ```
  "'Smitty' John Jones"       →  given="John"  · boundary
  ```

**Because:** a person set down as a nickname plus one name word is being identified by surname.

```
"'Smitty' Jones"            →  family="Jones"
```

**Accepted:**

- The count does not set suffixes aside, so a nickname plus one name word plus a suffix reads the name word as given and leaves the family empty.
  ```
  "'Smitty' Jones Jr."        →  family=""
  ```
- A title counts against the count too, but H1 then reads the title-plus-one-word name that is left, so the family is named after all — unless the title is a given-name title, which keeps the word in `given` and leaves no family, exactly as it does anywhere else.
  ```
  "'Smitty' Dr. Jones"        →  family="Jones"
  "'Smitty' Sir John"         →  given="John"
  ```
- A marker-led clause is a maiden clause and not a nickname one (M3), so this rule does not reach a name written that way, and the one name word keeps the reading the bare spelling gives it. That reading is the family name all the same, M4 reaching both spellings from the other side. The two rules agree on THIS name and not in general: M4 counts name words alone, so where a suffix stands beside them it fires and this rule declines. The first Accepted bullet reads a bare nickname-plus-word-plus-suffix name as given with no family, and the same name carrying a maiden clause reads family instead.
  ```
  "Smith (née Jones)"         →  family="Smith"
  ```

---
**Signal:** count
**history:** decisions/N3 · **implemented:** nameparser/_pipeline/_assign.py
