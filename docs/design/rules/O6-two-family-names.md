# O6 — two family names

**When:** two-family-name handling is active and a name with no family comma has three or more name words, as in "Gabriel García Márquez".

**Then:** the family name takes the name word beside it, so the last two name words are the family — the first two under a family-first order.

- **Under the default given-first order** the middle word standing right before the family joins it, and any middles before that stay middles.
  ```
  "Gabriel García Márquez"  two_family_names  →  family="García Márquez"
  "Ana María García López"  two_family_names  →  middle="María"
  ```
- **Under a family-first order** the word after the family joins it, and what is left is laid out as the positions after a family, as P1's family-first fold lays out its own remainder.
  ```
  "García Márquez Gabriel"  family-first+two_family_names  →  given="Gabriel"
  "García Márquez Ana María"  family-first-given-last+two_family_names  →  given="María"
  ```
- **A name word is counted as P1's fold counts one**, so a particle run counts with the word it attaches to: "de la Vega" is one word and takes the word before it.
  ```
  "Juan Pérez de la Vega"  two_family_names  →  family="Pérez de la Vega"
  ```
- **Titles, suffixes and nicknames are no name words**, and a comma that sets off only suffixes leaves the name before it to this rule.
  ```
  "Gabriel García Márquez Jr."  two_family_names  →  family="García Márquez"
  "Dr. Ana García López"  two_family_names  →  family="García López"
  "Gabriel García Márquez, PhD"  two_family_names  →  family="García Márquez"
  "Ana García (Anita) López"  two_family_names  →  family="García López"
  ```

**Because:** across Spain and most of Latin America a person carries two family names, the father's and then the mother's, and writes both after the given names. Given-first, that name is the same string shape as a name with a middle name, so no rule can read it from the words; the caller who knows the data is written that way says so.

```
"Gabriel García Márquez"    →  family="Márquez"  · boundary
"Ana García"  two_family_names  →  family="García"  · boundary
```

**Except:**

- **A family that already holds two words keeps what it has**: words a connective joins count as their words, a hyphen joins two words without making them one, and a particle chain counts the words it chained.
  ```
  "José María Ortega y Gasset"  two_family_names  →  family="Ortega y Gasset"
  "Ana María García-López"  two_family_names  →  family="García-López"
  "Ana María de la Vega Rodríguez"  two_family_names  →  family="de la Vega Rodríguez"
  ```
- **A family comma decides by itself**, so the part before it is the whole family.
  ```
  "López, Ana García"  two_family_names  →  family="López"
  "García López, Ana"  two_family_names  →  family="García López"
  ```
- **A name part that is one unit moves whole or not at all**: a particle chain (P2) or a bound given-name pair (P5) is never split, and the rule declines where taking it would leave no given name.
  ```
  "Juan de la Vega Rodríguez"  family-first+two_family_names  →  family="Juan"
  ```

**Precedence:**

- **Against compound-family handling** ("Ana María García López" with both switches on): this rule reads first and O3 then folds whatever middles are left, so under the given-first order the two together read as O3 alone.
  ```
  "Ana María García López"  two_family_names+middle_as_family  →  family="María García López"
  ```
- **Against a patronymic rotation** ("Ivanov Ivan Ivanovich" with the East Slavic rotation on): the rotation wins, because it already decided which word is the family, and this rule finds no middle standing before that family to take.
- **Against a particle attached at the end of a family-first name** ("Beethoven Ludwig Maria van"): P6 attaches the particle first and this rule then takes the word after the family, leaving the particle where P6 put it.
  ```
  "Beethoven Ludwig Maria van"  family-first+two_family_names  →  family="van Beethoven Ludwig"
  ```

**Accepted:**

- A name with one family name behind two given names loses its second given name to the family, which is the shape the switch cannot tell from the one it is for: an Argentine name, most English ones and every Portuguese or Brazilian name, whose mother's family name comes first, read wrong under it. That is why it is off by default and a caller turns it on only for data written this way.
  ```
  "Juan Carlos Pérez"  two_family_names  →  family="Carlos Pérez"
  ```
- The rule counts words, not languages, so a particle surname of any origin takes the word before it.
  ```
  "Ana María van der Berg"  two_family_names  →  family="María van der Berg"
  ```
- The rule reports nothing: the caller declared the convention, as a declared order is followed without a report, and a report on most names of three words or more would teach the caller to ignore the field.

---
**Signal:** none in the name: a caller switch, which joins the name word beside the family to it
**history:** decisions/O6 · **implemented:** nameparser/_pipeline/_post_rules.py
