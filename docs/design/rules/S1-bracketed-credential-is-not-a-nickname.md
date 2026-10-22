# S1 — a bracketed credential is not a nickname

**When:** a clause enclosed in brackets or quotes stands in a name, as in "Andrew Perkins (MBA)".

**Then:** an enclosed clause whose content is suffix-shaped is not a nickname: the brackets or quotes are dropped and the content reads exactly as if written bare.

**Because:** brackets and quotes set off more than nicknames — credentials are routinely written parenthesized after a name, and a credential is recognizable by its form.

```
"Andrew Perkins (MBA)"      →  suffix="MBA"
"Andrew Perkins «MBA»"      →  suffix="MBA"
"Andrew Perkins (Andy)"     →  nickname="Andy"  · boundary
```

**Except:**

- **A clause of two or more words** is a nickname whatever it holds, and nothing is reported, unless it ends in a period: suffix-shaped is asked of the whole clause, and a run of words is suffix-shaped only by a final period.
  ```
  "John Smith (PhD MBA)"      →  nickname="PhD MBA"
  "John Smith (PhD MBA)"      →  ambiguities=()
  "John Smith (MBA PhD.)"     →  suffix="MBA PhD."  · boundary
  ```

- **A clause that is one member of the ambiguous class (S4) written without periods** stays a nickname, and the fork is reported: the word is also a name, so the brackets may hold the name the person goes by, an accepted cost (decisions/suffix-acronym-collisions). A credential standing in front of the brackets does not speak for it (S7), and a final period makes the clause suffix-shaped, a member's included.
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
**Signal:** shape: suffix-shaped content inside brackets or quotes
**implemented:** nameparser/_pipeline/_extract.py
