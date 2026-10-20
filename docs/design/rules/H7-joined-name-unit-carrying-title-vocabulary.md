# H7 — a joined name unit carrying title vocabulary

**When:** the one name unit a name leaves standing is more than one word and carries title vocabulary, as in "John of Prince".

**Then:** one name UNIT of more than one word carrying title vocabulary reports `title-or-name`, the fork there being whether the title word inside the unit is a title at all.

- **A join or a particle chain.** Usually a join (P3), and a particle chain (P4) is the same shape and reports too — `St van Bishop` reads family "van Bishop" with `bishop` title vocabulary inside it.
  ```
  "John of Prince"            →  ambiguities=("title-or-name",)
  "St van Bishop"             →  family="van Bishop"
  "St van Bishop"             →  ambiguities=("particle-or-given", "title-or-name")
  ```
- **The reach is every such join.** The clause reaches EVERY join whose non-leading member is TITLES vocabulary, not the one word that prompted it: `Smith and King`, `John and King`, `Smith and Bishop` and `John of Judge` all report it, as `John of Prince` and `Smith and Prince` do.
  ```
  "Smith and King"            →  ambiguities=("title-or-name",)
  "John of Judge"             →  ambiguities=("title-or-name",)
  ```
- **Behind a peeled title.** A join OPENING the name with a title word is a title run (H3) instead. Behind a peeled title the join is not: a title needs a following piece and the join is the last one, so `Attorney General of Minnesota` and `Deputy Secretary of State` keep `Attorney` and `Deputy` as the title and report the rest — the two corpus names the clause reached on 2026-09-08, and `General` or `Secretary` being a title is exactly the fork.
  ```
  "Attorney General of Minnesota"  →  title="Attorney"
  "Attorney General of Minnesota"  →  ambiguities=("title-or-name",)
  ```
- **Nothing in front of the join silences the clause**, a title, a maiden name or a claimed word each deciding which FIELD the unit takes and none of them whether the word inside it is a title. The other measured inputs are pinned in the case table rather than here.
  ```
  "Dr. Smith and Prince"      →  ambiguities=("title-or-name",)
  ```
- **A unit of one word is H4's**: where the title peel leaves one word standing and that word is title vocabulary, H4's title half reports the same kind.

**Because:** a word joined into a name unit may be a second name that happens to be title vocabulary or a title written inside the name, and nothing in the writing says which. The doubt is whether the word is a title, not which field the unit takes.

```
"Prince of Wales"           →  title="Prince of Wales"  · boundary
"Prince of Wales"           →  ambiguities=()
```

**Accepted:**

- That reach is the king/judge/bishop collision set met inside a join, and the report is the honest answer there rather than a misfire — a second surname that is also title vocabulary is exactly the doubt the kind names, and those words stay in the vocabulary for the addressing forms, which is decisions/vocabulary-collisions' call.

---
**Signal:** count: one name unit left standing, more than one word, holding title vocabulary
**history:** decisions/H7 · **implemented:** nameparser/_pipeline/_assign.py
