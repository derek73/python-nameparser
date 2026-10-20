# A2 — the empty name

**When:** an input holds no name content, no letter or digit, as in ".,".

**Then:** a name with no name content parses to the empty name — every field empty, false as a boolean — while ambiguities born from its punctuation survive on the empty result.

**Because:** an input with no name content names nobody, and saying so beats inventing fields from punctuation.

```
".,"                        →  family=""
"("                         →  ambiguities=("unbalanced-delimiter",)
"John . Smith"              →  family="Smith"  · boundary
```

---
**Signal:** count: no name content, no letter or digit, in the input
**history:** decisions/A2 · **implemented:** nameparser/_pipeline/_assemble.py
