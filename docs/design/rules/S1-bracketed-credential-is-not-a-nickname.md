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

- **A clause of two or more words** is not suffix-shaped, whatever it holds, unless an ASCII period stands last before its closer: suffix-shaped is asked of the whole clause, so a run of credentials keeps its brackets or quotes and reads as its pair reads it, a nickname in a nickname pair.
  ```
  "John Smith (PhD MBA)"      →  nickname="PhD MBA"
  "John Smith (PhD MBA)"      →  ambiguities=()
  "John Smith (MA PhD)"       →  ambiguities=("suffix-or-nickname",)
  "John Smith (MBA PhD.)"     →  suffix="MBA PhD."  · boundary
  ```

- **A clause that is one member of the ambiguous class (S4) written without periods** is not suffix-shaped, so in a nickname pair it stays a nickname, and the fork is reported, as it is for such a member anywhere in a nickname: the word is also a name, so the brackets may hold the name the person goes by, an accepted cost (decisions/suffix-acronym-collisions). A credential standing in front of the brackets does not speak for it (S7), and a final period makes the clause suffix-shaped, a member's included.
  ```
  "John Smith (MA)"           →  nickname="MA"
  "John Smith (MA)"           →  ambiguities=("suffix-or-nickname",)
  "John Smith PhD (MA)"       →  nickname="MA"
  "John Smith (M.A.)"         →  suffix="M.A."  · boundary
  "John Smith (MA.)"          →  suffix="MA."  · boundary
  ```

**Precedence:**

- **A bracketed clause led by a maiden marker** ("Jane Smith (née Jr.)"): suffix-shaped content is taken here first, and the clause is no maiden name (M3), so M2's delimiter precedence never reaches it.
- **A clause M3 reads as a maiden name** ("Jane Smith (née Jones)"): its content is not suffix-shaped, so this rule leaves it to M3; the marker-led clause that is suffix-shaped is the bullet above.

---
**Signal:** shape: suffix-shaped content inside brackets or quotes
**history:** decisions/S1 · **implemented:** nameparser/_pipeline/_extract.py
