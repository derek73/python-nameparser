# S1 — a bracketed credential is not a nickname

**When:** a bracketed clause stands in a name, as in "Andrew Perkins (MBA)".

**Then:** a bracketed clause whose content is suffix-shaped is not a nickname: the brackets are dropped and the content reads exactly as if written bare.

**Because:** brackets set off more than nicknames — credentials are routinely written parenthesized after a name, and a credential is recognizable by its form.

```
"Andrew Perkins (MBA)"      →  suffix="MBA"
"Andrew Perkins (Andy)"     →  nickname="Andy"  · boundary
```

**Except:**

- **A clause that is one member of the ambiguous class (S4), not ending in a period,** stays a nickname, and the fork is reported: the word is also a name, so the brackets may hold the name the person goes by, an accepted cost (decisions/suffix-acronym-collisions). A credential standing in front of the brackets does not speak for it (S7), and a final period makes the clause suffix-shaped, a member's included.
  ```
  "John Smith (MA)"           →  nickname="MA"
  "John Smith (MA)"           →  ambiguities=("suffix-or-nickname",)
  "John Smith PhD (MA)"       →  nickname="MA"
  "John Smith (M.A.)"         →  suffix="M.A."  · boundary
  "John Smith (MA.)"          →  suffix="MA."  · boundary
  ```

**Precedence:**

- **A bracketed clause led by a maiden marker** ("Jane Smith (née Jr.)"): suffix-shaped content is taken here first, and the clause is no maiden name (M3), so M2's delimiter precedence never reaches it.

---
**Signal:** shape: suffix-shaped content inside brackets
**implemented:** nameparser/_pipeline/_extract.py
