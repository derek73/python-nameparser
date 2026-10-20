# R1 — fields are views of the parsed words

**When:** a field of a parsed name is read, as in "Dr. Juan Q. Xavier de la Vega III".

**Then:** every field is a view computed from the parsed words at read time, joining its words in written order — except folded family words — O3's fold and, since #379, P6's attached tussenvoegsel — which render before the rest of the family wherever they stood in the string.

- **Words are separated as the writer separated them.** The suffix view is the one place this is visible, because it is the only field that can hold parts the writer comma-separated: a run of post-nominals written with spaces renders with spaces, and one written with commas keeps them.
- **The separator is the comma the writer typed**, read off the words' positions once their roles are known; a delimiter the configuration names is a separator too, and so is any name word standing between two post-nominals.

**Because:** a field is a way of reading the parse, not a stored string.

```
"Dr. Juan Q. Xavier de la Vega III"  →  family="de la Vega"
"Hassan, Mohamad Ahmad Ali"  middle_as_family  →  family="Ahmad Ali Hassan"
"Hassan, Mohamad Ahmad Ali"          →  family="Hassan"  · boundary
"Smith, MD PhD"                      →  suffix="MD PhD"
"John Smith MD PhD"                  →  suffix="MD PhD"
"John Smith, MD, Bart"               →  suffix="MD, Bart"
"Smith, John, PhD - i Soler" extra_suffix_delimiters-dash →  suffix="PhD, i Soler"
```

**Accepted:**

- A suffix value handed to revise() derives its entries the same way, from the value's own commas, so a name's rendered suffix revises back to itself wherever the value's words read as the whole name read them — a glued CJK honorific peels off an initial in a bare value where the whole name kept it glued, one corpus name in the measurement decisions/R1 records. A delimiter the configuration names parts a value only where the value's own words, read as a name, give it a tail segment for the core to be dropped on; a run of post-nominals has none, with or without a comma of its own, so there the delimiter stays a word of the run — write a comma at the boundary instead. (The shape needs a field revised after the parse, so no example line.)

---
**Signal:** none in the name: the parsed words, their roles and the separators the writer typed between them
**history:** decisions/R1 · **implemented:** nameparser/_parser.py, nameparser/_pipeline/_post_rules.py, nameparser/_types.py
