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

- **Where a suffix stands beside them, an initial (T5, T4), a bound given name (P5) or a particle (P4) keeps the reading it already has**, the suffix leaving the field to that reading; M4 keeps the first two and flips a particle, and a given name written short (H2) is none of the three, so this rule decides it.
  ```
  "'Smitty' J. Jr."           →  given="J."
  "'Smitty' Abdul Jr."        →  given="Abdul"
  "'Smitty' de Jr."           →  given="de"
  ```

**Precedence:**

- **A title word left as the one name word is H4's**, whose doubt is whether the word is a title at all, so it keeps H4's reading by convention and its report.
  ```
  "'Smitty' Pope Jr."         →  given="Pope"
  "'Smitty' Pope Jr."         →  ambiguities=("title-or-name",)
  ```

**Accepted:**

- A surname the suffix vocabulary also holds, whole or as one of its period-joined chunks, written beside a bracketed note that is not a nickname, is read as the suffix, and the given name left beside it reads as the family name with nothing reported.
  ```
  "Rewati Od (Mahar)"         →  family="Rewati"
  "Sumnime D.C(Oli)"          →  family="Sumnime"
  ```
- The nickname may stand in any part of the name, and so may a bracketed clause read later as a credential (S1), but the one name word must stand in the first: a nickname alone before a comma leaves the word in the part after it, where neither the count nor the suffix reaches.
  ```
  "Jones Jr., 'Smitty'"       →  family="Jones"
  "Jones (PhD) Jr."           →  family="Jones"
  "'Smitty', Jones Jr."       →  given="Jones"
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
