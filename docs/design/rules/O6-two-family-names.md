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
- **The family keeps the two as units**, the one written second being the second-surname view (R10), whichever of the two the rule took.
  ```
  "Gabriel García Márquez"  two_family_names  →  surname2="Márquez"
  "García Márquez Gabriel"  family-first+two_family_names  →  surname2="Márquez"
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
  "Ana María García–López"  two_family_names  →  family="García–López"
  "Ana María García－López"  two_family_names  →  family="García－López"
  "Ana María de la Vega Rodríguez"  two_family_names  →  family="de la Vega Rodríguez"
  ```
- **A family comma decides by itself**, so the part before it is the whole family.
  ```
  "López, Ana García"  two_family_names  →  family="López"
  "García López, Ana"  two_family_names  →  family="García López"
  ```
- **A family comma with nothing before it still names no family** (C15), and the name after it reads as the default reads it.
  ```
  ", Ana García López"  two_family_names  →  family=""
  ```
- **What is taken must be one name word a family name could be**: a part counting as two words (a hyphenated given name, a bound given-name pair, P5) stays where it is, and so do an initial written alone, which writes a given name, and a mark or number with no letter in it. A particle chain (P2) is never split, so where taking it would leave no given name the rule declines.
  ```
  "Ana María-José López"  two_family_names  →  family="López"
  "Ana abdul Rahman López"  two_family_names  →  family="López"
  "Ana M. García"  two_family_names  →  family="García"
  "Ana María García - López"  two_family_names  →  family="López"
  "Ana María 3 López"  two_family_names  →  family="López"
  "Juan de la Vega Rodríguez"  family-first+two_family_names  →  family="Juan"
  ```
- **An order a name's script set is not a declared one** (W4), and no script it keys writes two family names as separate words, so a name its script reads in an order other than the declared `name_order` is left alone.
  ```
  "王 小 明"  two_family_names  →  family="王"
  "王 小 明"  family-first-given-last+two_family_names  →  family="王"
  ```

**Precedence:**

- **Against compound-family handling** ("Ana María García López" with both switches on): this rule reads first and O3 then folds whatever middles are left, so under the given-first order the two together read as O3 alone.
  ```
  "Ana María García López"  two_family_names+middle_as_family  →  family="María García López"
  ```
- **Against a patronymic rotation** ("Ivanov Ivan Ivanovich" with the East Slavic rotation on): where the rotation fires it wins, because it already decided which word is the family, and this rule finds no middle standing before that family to take. Where it does not fire, this rule reads the name as any other (Accepted).
- **Against P1's family-first reach** ("de Mesnil Jean Paul" under a family-first order): this rule wins and the family takes one name word past P1's one, because the switch is the caller saying the family holds two.
  ```
  "de Mesnil Jean Paul"  family-first+two_family_names  →  family="de Mesnil Jean"
  ```
- **Against a particle attached at the end of a family-first name** ("Beethoven Ludwig Maria van"): P6 attaches the particle first and this rule then takes the word after the family, leaving the particle where P6 put it.
  ```
  "Beethoven Ludwig Maria van"  family-first+two_family_names  →  family="van Beethoven Ludwig"
  ```

**Accepted:**

- A name with one family name behind two given names loses its second given name to the family, which is the shape the switch cannot tell from the one it is for: most Argentine and English names of three words or more read wrong under it, and so do Portuguese and Brazilian names whose writer gave the last family name alone as the family. That is why it is off by default and a caller turns it on only for data written this way.
  ```
  "Juan Carlos Pérez"  two_family_names  →  family="Carlos Pérez"
  ```
- A patronymic is a name word like any other here, a patronymic rule on or off, so where no rotation fired it can join the family.
  ```
  "Petrov Ivan Sergeevich"  family-first+two_family_names  →  family="Petrov Ivan"
  ```
- A lone particle the declared order left as the family counts as one word, R2 reading it as an ordinary name word, so the word after it joins.
  ```
  "van Gogh Ana María"  family-first+two_family_names  →  family="van Gogh"
  ```
- Where a name's script order and the declared one agree, nothing tells the two apart, so under a declared family-first order a spaced Han or Hangul name is read like any other.
  ```
  "王 小 明"  family-first+two_family_names  →  family="王 小"
  ```
- Initials written run together carry no initial's shape, and neither does an abbreviated given name, so either is taken.
  ```
  "Ana J.R. García"  two_family_names  →  family="J.R. García"
  ```
- The rule counts words, not languages, so a particle surname of any origin takes the word before it.
  ```
  "Ana María van der Berg"  two_family_names  →  family="María van der Berg"
  ```
- The rule reports nothing: the caller declared the convention, as a declared order is followed without a report, and a report on most names of three words or more would teach the caller to ignore the field.

---
**Signal:** none in the name: a caller switch, the family's words and the taken word's shape read as written to see whether the family already holds two
**history:** decisions/O6 · **implemented:** nameparser/_pipeline/_post_rules.py
