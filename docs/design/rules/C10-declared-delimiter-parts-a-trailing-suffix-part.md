# C10 — a declared delimiter parts a trailing suffix part

**When:** the policy declares a suffix delimiter and it stands in a trailing suffix part, as in "Smith, John, PhD - and MD".

**Then:** a delimiter the policy declares parts a trailing suffix part as a comma would: the words on each side of it read exactly as the parts of the same text written with a comma in its place, so no join, maiden clause or connective reaches across it.

- **The delimiter itself is dropped**, unless it stands alone as the whole of its part.
- **Only a trailing part is parted**: in the part before the first comma, or in the given part of the listing form (C8), the delimiter is a word (the second Accepted bullet).

**Because:** a caller who declares a suffix delimiter means it to separate suffixes as a comma does, and the simplest reading that honours that is one where it is a comma there.

```
"Smith, John, Puig - i Soler" extra_suffix_delimiters-dash →  suffix="Puig, i Soler"
"Smith, John, PhD - and MD" extra_suffix_delimiters-dash →  suffix="PhD, and MD"
"Smith, RN - CRNA" extra_suffix_delimiters-dash →  suffix="RN - CRNA"  · boundary
```

**Accepted:**

- A maiden marker in a part a declared delimiter separates takes no clause. The delimiter costs nothing here: a marker in a part after a suffix comma is an ordinary word with or without a core (M2), so 'Smith, John, MD née Jones Smith' takes none either. Releases 2.0 through 2.3 read past the delimiter and took the clause.
  ```
  "Smith, John, MD - née Jones Smith" extra_suffix_delimiters-dash →  suffix="MD, née Jones Smith"
  ```
- A delimiter core the policy names (T1) is a word here, not structure — v1 applied the delimiter to the suffix-comma form alone, and that limitation is kept as parity: the core in 'Smith, RN - CRNA' is a word under the policy as without it. Since #603 it is a word of the run the credential opens, so the part reads suffix "RN - CRNA" where 2.0 through 2.3, like v1, read given "RN".
  ```
  "Smith, RN - CRNA"          →  suffix="RN - CRNA"
  ```

---
**Signal:** separator: a delimiter the caller declared, inside a trailing suffix part
**history:** decisions/C10 · **implemented:** nameparser/_pipeline/_comma.py, nameparser/_pipeline/_group.py
