# P4 — a particle at the front of the name

**When:** a particle stands in the name's leading position, as in "Van Johnson".

**Then:** a particle in the name's leading position chains nothing: the words stay separate, and any surname reading the name gets comes from the fold (P1) or from position (O4), never from a join.

- **Chaining nothing is why a title before a leading particle changes nothing** (the title is not a name word), and why "Van Johnson" is a given-name reading at all.
  ```
  "Sir de Mesnil"             →  pieces=[["Sir"], ["de"], ["Mesnil"]]
  ```
- **An unlisted abbreviation before the particle is as transparent as a listed title**, since assign reads it as one (H2).
  ```
  "Xyz. van Johnson"          →  given="van"
  ```

**Because:** a particle links forward from inside a name; at the very front there is no name yet to be inside.

```
"Van Johnson"               →  given="Van"
"John van der Berg"         →  pieces=[["John"], ["van", "der", "Berg"]]  · boundary
```

**Except:**

- **A word in the leading titles that is both a title and a particle puts the name's leading position on itself**, so the particle behind it is inside a name ('Freiherr von Berg'); of several such words the last does, so no particle chains inside the titles (#624). The titles are those written, before H3 gives the last one back to the name, so each such word reads as a title unless H3 gives it back.
  ```
  "Freiherr St John Smith"    →  title="Freiherr St"
  "Freiherr St John Smith"    →  given="John"
  ```

---
**Signal:** position: a particle in the name's leading position
**history:** decisions/P2 · **implemented:** nameparser/_pipeline/_group.py, nameparser/_pipeline/_pieces.py
