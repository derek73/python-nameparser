# H4 — an input that is nothing but vocabulary still has to name somebody

**When:** an input holds no name word but vocabulary, title or post-nominal, as in "Lord Chancellor".

**Then:** an input whose only remaining name word after the title peel is itself title vocabulary reads that word as the name by convention and reports `title-or-name`; an input whose every word is post-nominal vocabulary reads its first word as a name and reports `suffix-or-name`.

- **A single title word** reads as a title with no name beside it and reports nothing: the peel took the whole string, so no word was left standing to be read as a name and no reading was chosen.
  ```
  "Dr."                       →  title="Dr."  · boundary
  "Dr."                       →  ambiguities=()
  ```
- **ONE site takes both halves** — the assignment that places the lone name word — so neither report depends on the declared order. Under the default order H1 retags the title-vocabulary word from given to family afterwards; under a declared family-first order the assignment places it in the family directly and H1 never runs. Same reading either way, so the same kind is reported either way.
- **Where H7 meets this rule**: a name unit of more than one word carrying title vocabulary reports `title-or-name` too, by H7, the fork there being whether the word inside the unit is a title.

**Because:** this is a name parser, not a title parser. Handed a string the title peel eats down to one last word which is itself title vocabulary, it still has to name somebody, and that word is the only candidate there is — a guess fixed in advance, so the same input reads the same way every time, not a claim that the word is a surname. The same reasoning covers a string that is nothing but post-nominal vocabulary: something has to be the name.

```
"Lord Chancellor"           →  family="Chancellor"
"Lord Chancellor"           →  ambiguities=("title-or-name",)
"The Right Hon. the President of the Queen's Bench Division"  →  family="Division"
"The Right Hon. the President of the Queen's Bench Division"  →  ambiguities=("title-or-name",)
"Dr. Pope"                  →  ambiguities=("title-or-name",)
"Dr. Pope MD"               →  ambiguities=("title-or-name",)
"Rinpoche"                  →  ambiguities=("suffix-or-name",)
"QC MP"                     →  given="QC"
"Dr. Smith"                 →  ambiguities=()
```

**Except:**

- **A title in front takes the input out of the suffix half**, which is reached only where no title was peeled first. What it does NOT do is take the input out of the rule: the title run leaves a name word standing (H3), and where that word is title vocabulary the TITLE half claims it — `Dr. Pope MD` reports `title-or-name` on `Pope`, while `RA DDS` reports nothing, `DDS` being no title.
  ```
  "RA DDS"                    →  ambiguities=()
  ```

**Precedence:**

- **A dotted lone credential** ("Jr."): `Jr.` is post-nominal vocabulary and still reads as a title, H2's opening-abbreviation shape outranking the vocabulary where it fires — so the suffix half never sees a dotted lone credential. A credential that is also a given name written short is that given name instead, by H2's own precedence ("Ma.").
  ```
  "Jr."                       →  title="Jr."
  "Jr."                       →  ambiguities=()
  "Ma."                       →  given="Ma."
  ```

**Accepted:**

- The suffix half is scoped to names no script order placed, so a lone CJK honorific written by itself — さん, 씨, 선생님 — reports nothing. The same shape, read through the glued-honorific rules (W2) and the script's own order, and left to the arc that revisits those readings. That silence is a SCOPE on the script rule having placed the name, not a claim about the honorific: a caller who declares no script orders at all gets the report on the same input, since nothing then resolves the order and the word reaches the carve-out as any other lone credential does. The pair is pinned in the case table rather than here, a policy that empties the script table having no example spelling in this document.


---
**Signal:** count: no name word left but vocabulary, title or post-nominal
**history:** decisions/H4 · **implemented:** nameparser/_pipeline/_assign.py
