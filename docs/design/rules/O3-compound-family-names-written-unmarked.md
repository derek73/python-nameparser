# O3 — compound family names written unmarked

**When:** compound-family handling is active, as in "Hassan Mohamad Ali".

**Then:** every middle word joins the family name and is rendered before it; no word is a middle name.

**Because:** several traditions write compound family names unmarked, so that every word after the given name belongs to the family name.

```
"Hassan Mohamad Ali"  middle_as_family  →  family="Mohamad Ali"
"Hassan Mohamad Ali"                    →  family="Ali"  · boundary
```

---
**Signal:** none in the name: a caller switch, which joins every middle word to the family
**implemented:** nameparser/_pipeline/_post_rules.py
