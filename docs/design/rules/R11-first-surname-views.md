# R11 — the first-surname views

**When:** two-family-name handling has read a name's family as two name units (O6), as in "Juan Pérez de la Vega", or compound-family handling has folded middle names into it (O3).

**Then:** the family's first name unit, the one written first, makes the first-surname view, split into its particles and its base as the family's own views split the whole family (R2), and a family read as one unit is its own first surname.

**Because:** CLDR's `surname-prefix` and `surname-core` describe the first of two surnames, and CLDR has no prefix field for the second, so a pattern filling them needs the first unit told apart. A base joining words of both surnames is nobody's name, and it sorts and abbreviates wrongly wherever a caller reads the base as the surname to file under. Only O6 knows where the first unit ends and only O3 which words it folded in, so the views read the marks those rules leave and never a position.

```
"Juan Pérez de la Vega"  two_family_names  →  surname1="Pérez"
"Juan Pérez de la Vega"  two_family_names  →  surname1_particles=""
"Juan Pérez de la Vega"  two_family_names  →  surname1_base="Pérez"
"Juan Pérez de la Vega"  two_family_names  →  family_base="Pérez Vega"
"Juan de la Vega del Valle"  two_family_names  →  surname1="de la Vega"
"Juan de la Vega del Valle"  two_family_names  →  surname1_particles="de la"
"Juan de la Vega del Valle"  two_family_names  →  surname1_base="Vega"
"Gabriel García Márquez"  two_family_names  →  surname1="García"
"García Márquez Gabriel"  family-first+two_family_names  →  surname1="García"
"García Márquez Ana María"  family-first-given-last+two_family_names  →  surname1="García"
"Dr. Ana García López Jr."  two_family_names  →  surname1="García"
"Juan de la Vega"  two_family_names  →  surname1_base="Vega"
"Juan de la Vega"           →  surname1="de la Vega"  · boundary
"Juan de la Vega"           →  surname1_particles="de la"
"Pérez de la Vega, Juan"  two_family_names  →  surname1_base="Pérez Vega"
```

**Except:**

- **Middle words folded into the family belong to neither unit**, so under compound-family handling (O3) the first-surname views leave them out, as the second-surname view does (R10), whether the family holds one unit or two.
  ```
  "Ana María García López"  two_family_names+middle_as_family  →  surname1="García"
  "Ana María García López"  two_family_names+middle_as_family  →  family="María García López"
  "Ana María García López"  middle_as_family  →  surname1="López"
  "García López, Ana María"  two_family_names+middle_as_family  →  surname1="García López"
  ```
- **A particle attached at the end of a family-first name belongs to the first unit**, the family it was attached to (P6), and stands before it there as it does in the family.
  ```
  "Beethoven Ludwig Maria van"  family-first+two_family_names  →  surname1="van Beethoven"
  "Beethoven Ludwig Maria van"  family-first+two_family_names  →  surname1_particles="van"
  ```

**Accepted:**

- Initials keep reading the whole family's base (R3): both surnames are the person's name words, and a monogram of the first alone is a render pattern's to build from these views.
  ```
  "Juan Pérez de la Vega"  two_family_names  →  initials="J. P. V."
  ```
- A family O6 leaves whole is one unit, so where a connective, a hyphen or a family comma already joins two family names the views are the family's, as the second-surname view is empty there (R10's Accepted).
  ```
  "Ana María García-López"  two_family_names  →  surname1="García-López"
  "José María Ortega y Gasset"  two_family_names  →  surname1_base="Ortega y Gasset"
  ```
- A family word with no reading, one that `replace()` or `Parser.revise()` wrote or in a name unpickled from 2.x, is in no unit, so such a family reads as one and the views are the family's.
- A first unit of a lone particle, which O6 leaves where it reads a particle and a name word after a family-first family as two surnames, splits as the family does, the particle working there, so its base is empty; the misreading is O6's, and the two units' particles and bases still add up to the family's.
  ```
  "van Gogh Vincent"  family-first+two_family_names  →  surname1_base=""
  ```
- A fold into a family the name left empty, behind a family comma with nothing before it (C15), has no first unit to keep apart from the folded words, so they are the views.
  ```
  ", John Paul"  middle_as_family  →  surname1="Paul"
  ```

---
**Signal:** none in the name: caller switches, read through the unit two-family-name handling took and the family compound-family handling folded into
**history:** decisions/R11 · **implemented:** nameparser/_types.py, nameparser/_pipeline/_post_rules.py, nameparser/_pipeline/_assemble.py
