# R10 — the second-surname view

**When:** two-family-name handling has read a name's family as two name units (O6), as in "Gabriel García Márquez".

**Then:** the family's second name unit, the one written second, makes the second-surname view, the family keeping both units, and every other name has an empty one.

**Because:** across Spain and most of Latin America a person carries two family names, and a caller addressing or sorting by the first one, or filling CLDR's `surname2` or Wikidata's second-family-name field, needs to know where the second begins. Only O6 knows that, since only the caller's switch says the family holds two, so the view reads the unit O6 took and never a position.

```
"Gabriel García Márquez"  two_family_names  →  surname2="Márquez"
"Gabriel García Márquez"  two_family_names  →  family="García Márquez"
"Ana María García López"  two_family_names  →  surname2="López"
"Juan Pérez de la Vega"  two_family_names  →  surname2="de la Vega"
"García Márquez Gabriel"  family-first+two_family_names  →  surname2="Márquez"
"García Márquez Ana María"  family-first-given-last+two_family_names  →  surname2="Márquez"
"Dr. Ana García López"  two_family_names  →  surname2="López"
"Gabriel García Márquez Jr."  two_family_names  →  surname2="Márquez"
"Gabriel García Márquez, PhD"  two_family_names  →  surname2="Márquez"
"Ana García (Anita) López"  two_family_names  →  surname2="López"
"Gabriel García Márquez"    →  surname2=""  · boundary
"Ana García"  two_family_names  →  surname2=""
"Lloyd Webber, Andrew"  two_family_names  →  surname2=""
"García López, Ana"  two_family_names  →  surname2=""
", Ana García López"  two_family_names  →  surname2=""
```

**Except:**

- **Middle words folded into the family belong to neither unit**, so under compound-family handling (O3) they stand before the first and the view is the second unit alone.
  ```
  "Ana María García López"  two_family_names+middle_as_family  →  surname2="López"
  "Ana María García López"  two_family_names+middle_as_family  →  family="María García López"
  ```
- **A particle attached at the end of a family-first name belongs to the first unit**, the family it was attached to (P6), so the second unit is the word O6 took after it.
  ```
  "Beethoven Ludwig Maria van"  family-first+two_family_names  →  surname2="Ludwig"
  ```

**Accepted:**

- A family O6 leaves whole is one unit to the view, so where a connective, a hyphen or a particle chain already joins two family names the name has two and the view is empty, as O6 counts them.
  ```
  "José María Ortega y Gasset"  two_family_names  →  surname2=""
  "Ana María García-López"  two_family_names  →  surname2=""
  "Ana María de la Vega Rodríguez"  two_family_names  →  surname2=""
  ```
- A family comma marks nothing, even where the part before it holds two family names, since nothing in it tells them from one compound name.
- Where O6 reads a given name into the family, the family's own name is the view: the shape the switch cannot tell from the one it is for (O6's Accepted).
  ```
  "Juan Carlos Pérez"  two_family_names  →  surname2="Pérez"
  ```
- A word of the second unit keeps the reading it took, so a patronymic there is in both views (R9).
  ```
  "Ali Hassan bin Ahmad"  two_family_names  →  surname2="bin Ahmad"
  "Ali Hassan bin Ahmad"  two_family_names  →  patronymic="bin Ahmad"
  ```
- The second unit's particles are in the view, which has no particle field of its own.
- A family word with no reading, one that `replace()` or `Parser.revise()` wrote or in a name unpickled from 2.x, is in no unit, since nothing records which one it was.

---
**Signal:** none in the name: a caller switch, read through the unit two-family-name handling took
**history:** decisions/R10 · **implemented:** nameparser/_types.py, nameparser/_pipeline/_post_rules.py, nameparser/_pipeline/_assemble.py
