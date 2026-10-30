# O7 — two given names

**When:** two-given-name handling is active and the given name stands beside a middle name, as in "Juan Carlos Pérez".

**Then:** the given name takes the middle unit beside it, so the given name is two name units and any middles past them stay middles.

- **Under the default given-first order, and after a family comma**, the middle written right after the given name joins it.
  ```
  "Juan Carlos Pérez"  two_given_names  →  given="Juan Carlos"
  "Ana María José Pérez"  two_given_names  →  middle="José"
  "Pérez, Juan Carlos"  two_given_names  →  given="Juan Carlos"
  ```
- **Under a family-first order** the middle after the given name joins it, and under the family-first order with the given name last the middle before it, so the two stay in the order they were written.
  ```
  "García Juan Carlos"  family-first+two_given_names  →  given="Juan Carlos"
  "García Antonio Juan Carlos"  family-first-given-last+two_given_names  →  given="Juan Carlos"
  "García Antonio Juan Carlos"  family-first-given-last+two_given_names  →  middle="Antonio"
  ```
- **A unit is counted as O6 counts a name word**, so a particle chain the name left in the middle joins with its words: a given name that a particle and its word complete reads whole.
  ```
  "María del Carmen de la Vega"  two_given_names  →  given="María del Carmen"
  "Maria do Carmo da Silva"  two_given_names  →  family="da Silva"
  ```
- **An initial is taken**, since it writes a given name short.
  ```
  "J. Carlos Pérez"  two_given_names  →  given="J. Carlos"
  ```
- **Titles, suffixes, nicknames and a maiden name are no name units**, and a comma that sets off only suffixes leaves the name before it to this rule.
  ```
  "Dr. Juan Carlos Pérez Jr."  two_given_names  →  given="Juan Carlos"
  "Juan Carlos Pérez, PhD"  two_given_names  →  given="Juan Carlos"
  "Juan Carlos Pérez née López"  two_given_names  →  given="Juan Carlos"
  ```

**Because:** across Spain, Portugal and Latin America a person may carry a compound given name, such as María José or Juan Carlos, and has no middle name, so every given-name word the name holds is its given name. Written given-first, that name is the same string shape as a name with a middle name, so no rule can read it from the words; the caller who knows the data is written that way says so.

```
"Juan Carlos Pérez"    →  given="Juan"  · boundary
"Juan Pérez"  two_given_names  →  given="Juan"  · boundary
"Juan Carlos"  two_given_names  →  family="Carlos"  · boundary
```

**Except:**

- **A given name that already holds two words keeps what it has**: a hyphen joins two words, and so does a bound given-name pair (P5), so neither takes a third.
  ```
  "María-José Ana López"  two_given_names  →  given="María-José"
  "abdul Rahman Ali Khan"  two_given_names  →  middle="Ali"
  ```
- **What is taken must be one name word**: a part counting as two words stays where it is, and so does a mark or number with no letter in it; nor does a given name with no letter in it take anything, being no name to complete.
  ```
  "Ana María-José López"  two_given_names  →  middle="María-José"
  "Juan 3 Pérez"  two_given_names  →  middle="3"
  "11 Elizabeth Mcguinness"  two_given_names  →  middle="Elizabeth"
  ```
- **A patronymic is no given name**: a word that an ending rule reads as a patronymic (R9) stays in the middle, and so does the father's name in front of a Turkic marker.
  ```
  "Ivan Ivanovich Ivanov"  east-slavic+two_given_names  →  given="Ivan"
  "Ivan Ivanovich Ivanov"  east-slavic+two_given_names  →  middle="Ivanovich"
  ```
- **An order a name's script set is not a declared one** (W4), so a name its script reads in an order other than the declared `name_order` is left alone.
  ```
  "王 小 明"  two_given_names  →  given="小"
  ```

**Precedence:**

- **Against two-family-name handling** ("Gabriel García Márquez" with both switches on): that rule reads first, since the caller who turns both on says the family holds two names, and this rule takes from the middles it leaves. A name of three words then keeps one given name, and a name of four reads two and two.
  ```
  "Gabriel García Márquez"  two_family_names+two_given_names  →  given="Gabriel"
  "María José García López"  two_family_names+two_given_names  →  given="María José"
  "María José García López"  two_family_names+two_given_names  →  family="García López"
  ```
- **Against compound-family handling** ("Hassan Mohamad Ali" with both switches on): this rule reads first, as a bound given-name pair (P5) joins before the fold, and O3 then folds whatever middles are left.
  ```
  "Hassan Mohamad Ali Omar"  two_given_names+middle_as_family  →  given="Hassan Mohamad"
  "Hassan Mohamad Ali Omar"  two_given_names+middle_as_family  →  family="Ali Omar"
  ```
- **Against a patronymic rotation** ("Ivanov Ivan Ivanovich" with the East Slavic rotation on): the rotation decides the order first, and the patronymic it leaves in the middle is no given name (above).

**Accepted:**

- A name whose second given-name word is a middle name gains it in the given name, which is the shape the switch cannot tell from the one it is for: most English names of three words or more read that way under it. That is why it is off by default and a caller turns it on only for data written this way.
  ```
  "John Quincy Adams"  two_given_names  →  given="John Quincy"
  ```
- A particle chain the name left in the middle is taken whatever its language, so a Dutch name holding two particle surnames gives its first to the given name.
  ```
  "Vincent van Gogh van Beethoven"  two_given_names  →  given="Vincent van Gogh"
  ```
- A particle that ends the name chains every word after it into the family (P2), so a given name a particle completes is read only where a second particle starts the family: in "Maria do Carmo Silva" the family keeps "do Carmo Silva", the same string shape as "João da Silva Santos", whose family it is.
  ```
  "Maria do Carmo Silva"  two_given_names  →  family="do Carmo Silva"
  ```
- Where no ending rule is on, a patronymic is a name word like any other and joins the given name.
  ```
  "Ivan Ivanovich Ivanov"  two_given_names  →  given="Ivan Ivanovich"
  ```
- The rule reports nothing: the caller declared the convention, as O6's switch reports nothing.

---
**Signal:** none in the name: a caller switch, the given name's words and the taken unit's shape read as written
**history:** decisions/O7 · **implemented:** nameparser/_pipeline/_post_rules.py
