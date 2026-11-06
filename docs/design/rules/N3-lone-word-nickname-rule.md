# N3 — the lone-word nickname rule

**When:** a name is written as a nickname beside its name words, as in "'Smitty' Jones".

**Then:** a name that is only a nickname and one name word reads that word as the family name, whatever suffix stands beside them.

- **With two or more name words the ordinary positional reading applies.**
  ```
  "'Smitty' John Jones"       →  given="John"  · boundary
  ```

**Because:** a person set down as a nickname plus one name word is being identified by surname.

```
"'Smitty' Jones"            →  family="Jones"
"'Smitty' Jones Jr."        →  family="Jones"
"Jones (Smitty) PhD"        →  family="Jones"
"'Smitty' Jones Jr."        →  ambiguities=()
```

**Except:**

- **Where a suffix stands beside them, a word the vocabulary or its own shape has claimed keeps that claim** — an initial, a bound given name, a particle (T5, T4) — as it does under M4, the suffix leaving the field to the reading the word already has.
  ```
  "'Smitty' J. Jr."           →  given="J."
  "'Smitty' Abdul Jr."        →  given="Abdul"
  ```

**Accepted:**

- A surname the suffix vocabulary also holds, written beside a bracketed note that is not a nickname, is read as the suffix, and the given name left beside it reads as the family name with nothing reported.
  ```
  "Rewati Od (Mahar)"         →  family="Rewati"
  ```
- Without a suffix the claimed word reads as the family name all the same, since the count fires before anything asks what the word is, so a suffix moves an initial from the family to the given name.
  ```
  "'Smitty' J."               →  family="J."
  ```
- A title counts against the count too, but H1 then reads the title-plus-one-word name that is left, so the family is named after all — unless the title is a given-name title, which keeps the word in `given` and leaves no family, exactly as it does anywhere else.
  ```
  "'Smitty' Dr. Jones"        →  family="Jones"
  "'Smitty' Sir John"         →  given="John"
  ```
- A marker-led clause is a maiden clause and not a nickname one (M3), so this rule does not reach a name written that way, and the one name word keeps the reading the bare spelling gives it. That reading is the family name all the same, M4 reaching both spellings from the other side, and both rules set a suffix beside the word aside.
  ```
  "Smith (née Jones)"         →  family="Smith"
  ```

---
**Signal:** count
**history:** decisions/N3 · **implemented:** nameparser/_pipeline/_assign.py
