# S13 — a bracketed member settled by its writing

**When:** a clause that is one member of the ambiguous class (S4) stands in brackets or quotes after the name, as in "John Smith (MA)".

**Then:** where the member's writing settles it, written with a period inside it or in capitals in a name written in more than one case (S6), it is the suffix rather than the nickname, and nothing is reported.

- **The case is the name's**: it is asked of the name's own words and never of the clause's, so capitals settle nothing in a name written wholly in one case, and Title case leans to the name (S6).
- **After the name** means that no name word follows the clause, though a suffix or a maiden clause may.
- **It is the suffix, not read as if written bare** (S1): the brackets have already set it apart from the name's words, and bare, two letters each followed by a period but the last read as initials (S3).

**Because:** after the name, brackets hold either a credential or the name the person goes by, and the writing tells the two apart where the count of words cannot: credentials are written in capitals and with their periods, and names are not. Inside the name the same word let out of the brackets would read as a middle name, where the brackets more likely hold the name the person goes by. So only the clause after the name is settled.

```
"John Smith (MA)"           →  suffix="MA"
"John Smith (MA)"           →  ambiguities=()
"John Smith (M.A)"          →  suffix="M.A"
"JOHN SMITH (M.A)"          →  suffix="M.A"
"Smith, John (MA)"          →  suffix="MA"
"John Smith PhD (MA)"       →  suffix="PhD MA"
"John Smith (MA), PhD"      →  suffix="MA, PhD"
"John Smith (MA) née Jones" →  suffix="MA"
"John Smith «MA»"           →  suffix="MA"
"John Smith 「MA」"          →  suffix="MA"
"John Smith (Ed)"           →  nickname="Ed"  · boundary
```

**Except:**

- **A member in a name written in one case, or not in capitals**, is settled only by a period inside it: its case says nothing (S6), and it stays the nickname S1 reads.
  ```
  "JOHN SMITH (MA)"           →  nickname="MA"
  "JOHN SMITH (MA)"           →  ambiguities=("suffix-or-nickname",)
  "john smith (MA)"           →  nickname="MA"
  "John Smith (Ma)"           →  nickname="Ma"
  ```
- **A member standing inside the name or before it** stays the nickname, however it is written.
  ```
  "Jeffrey (JD) Bricken"      →  nickname="JD"
  "JEFFREY (JD) BRICKEN"      →  nickname="JD"
  "Jean 'JD' Smith"           →  nickname="JD"
  "Jean (M.A) Smith"          →  nickname="M.A"
  "Smith (MA), John"          →  nickname="MA"
  "(MA) John Smith"           →  nickname="MA"
  ```

**Accepted:**

- A member after a lone name word is the suffix where its writing settles it, and the word reads as a one-word name reads, given rather than the family name it was beside a nickname.
  ```
  "Jack (MA)"                 →  given="Jack"
  ```

---
**Signal:** position: a member of the ambiguous class alone in brackets or quotes after the name, its writing read as S6 reads capitals
**history:** decisions/S13 · **implemented:** nameparser/_pipeline/_group.py
