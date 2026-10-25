# C6 — an unlisted all-caps word needs the name's case contrast

**When:** an unlisted word written in capitals stands in the part after the comma, as in "John Smith, XYZ".

**Then:** an unlisted all-caps word joins the ambiguous credential class (C4, S9) in the part after the comma only where the name carries the contrast: one of its own words before the comma written the way a name is written in mixed case.

- **A word written the way a name is** holds a capital with its last cased letter lowercase — read after composing the word, passing over every non-letter and caseless letter and any lowercase letter whose capital is not a single letter, as ß's is not — with no period and not claimed by the vocabulary as a title, particle, connective, credential or generation.
  ```
  "MÜLLER WEIß, HANS"         →  given="HANS"  · boundary
  ```
- **A surname written in capitals ends in a capital whatever is glued in front of it, and a word written wholly in lowercase holds none**, so such a record keeps its given name beside its lowercase particles, titles and clauses ("GISCARD d'ESTAING, VALÉRY", 'LLOYD FitzGERALD, RONALD'), and a name written wholly in lowercase reads the listing form.

**Because:** capitals are a credential's writing only against a name written otherwise; a name written in capitals, or wholly in lowercase, says nothing about any word in it.

```
"John Smith, XYZ"           →  suffix="XYZ"
"John Smith, XYZ"  unlisted_caps_suffixes-off  →  given="XYZ"
"John Smith, LEED AP"       →  suffix="LEED AP"
"Smith, XYZ"                →  given="XYZ"  · boundary
"John Smith, PhD XYZ"       →  suffix="PhD XYZ"
"John Smith, PU-PH"         →  suffix="PU-PH"
"JOHN SMITH, PU-PH"         →  given="PU-PH"  · boundary
"Smith, PU-PH"              →  given="PU-PH"  · boundary
```

---
**Signal:** case contrast: a word before the comma written in mixed case the way a name is
**history:** decisions/C6 · **implemented:** nameparser/_pipeline/_comma.py
