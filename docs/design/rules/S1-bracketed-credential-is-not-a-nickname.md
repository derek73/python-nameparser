# S1 — a bracketed credential is not a nickname

**When:** a bracketed clause stands in a name, as in "Andrew Perkins (MBA)".

**Then:** a bracketed clause whose content is suffix-shaped is not a nickname: the brackets are dropped and the content reads exactly as if written bare.

**Because:** brackets set off more than nicknames — credentials are routinely written parenthesized after a name, and a credential is recognizable by its form.

```
"Andrew Perkins (MBA)"      →  suffix="MBA"
"Andrew Perkins (Andy)"     →  nickname="Andy"  · boundary
```

**Except:**

- **A member of the ambiguous class (S4) written without periods** anywhere in the clause keeps the clause a nickname, and the fork is reported: the word is also a name, so the brackets may hold the name the person goes by, an accepted cost (decisions/suffix-acronym-collisions). The company of a credential in front of it (S7) does not reach into the clause, and the dotted spelling is no member (S3).
  ```
  "John Smith (MA)"           →  nickname="MA"
  "John Smith (MA)"           →  ambiguities=("suffix-or-nickname",)
  "John Smith (PhD MA)"       →  nickname="PhD MA"
  "John Smith (M.A.)"         →  suffix="M.A."  · boundary
  ```

**Precedence:**

- **A bracketed clause led by a maiden marker** ("Jane Smith (née Jr.)"): suffix-shaped content is taken here first, and the clause is no maiden name (M3), so M2's delimiter precedence never reaches it.

---
**Signal:** shape: suffix-shaped content inside brackets
**implemented:** nameparser/_pipeline/_extract.py
